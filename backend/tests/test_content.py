import json

import pytest
import yaml

from app.content import loader
from app.content.models import Challenge
from app.content.schemas import render
from app.core.config import settings


def test_repository_content_is_valid():
    c = loader.load()
    assert len(c.tracks) == 15 and len(c.projects) == 5 and len(c.challenges) == 15


def test_committed_json_schemas_are_up_to_date():
    for fname, text in render().items():
        committed = (settings.content_dir / "schemas" / fname).read_text()
        assert json.loads(committed) == json.loads(text), f"{fname} is stale: run `make schemas`"


def _write(root, sub, name, data):
    d = root / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(yaml.safe_dump(data))


def test_invalid_content_names_file_and_field(tmp_path):
    for sub in ("tracks", "projects", "challenges"):
        (tmp_path / sub).mkdir()
    _write(tmp_path, "tracks", "bad.yaml", {"id": "bad", "name": "Bad", "status": "nope", "phase": 1,
                                            "description": "x"})
    with pytest.raises(loader.ContentError, match=r"bad\.yaml: status"):
        loader.load(tmp_path)


def test_project_must_reference_existing_challenges(tmp_path):
    for sub in ("tracks", "challenges"):
        (tmp_path / sub).mkdir()
    _write(tmp_path, "projects", "p.yaml", {"id": "pp", "name": "P", "status": "planned", "phase": 4,
                                            "summary": "s", "components": [], "topics": [],
                                            "challenges": ["ghost"]})
    with pytest.raises(loader.ContentError, match="unknown challenges"):
        loader.load(tmp_path)


BASE = {"id": "k8s-x", "name": "X", "difficulty": "beginner", "technology": "kubernetes", "description": "d"}


def test_available_challenge_must_be_complete():
    with pytest.raises(ValueError, match="missing: initial_state"):
        Challenge.model_validate({**BASE, "status": "available"})


def test_hints_must_be_three_progressive_levels():
    hints = [{"level": 2, "kind": "resource", "text": "a"}, {"level": 1, "kind": "direction", "text": "b"}]
    with pytest.raises(ValueError, match="levels 1, 2, 3"):
        Challenge.model_validate({**BASE, "status": "planned", "hints": hints})
