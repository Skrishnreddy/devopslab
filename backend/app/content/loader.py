"""Loads and validates content/ at startup. Invalid content stops the app with
the file and field at fault, so broken contributions fail fast."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from ..core.config import settings
from .models import SETUP_KINDS, Challenge, Lesson, Project, Track


class ContentError(Exception):
    pass


@dataclass
class Content:
    tracks: list[Track] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    challenges: list[Challenge] = field(default_factory=list)
    lessons: dict[str, Lesson] = field(default_factory=dict)

    def module(self, module_id: str):
        for t in self.tracks:
            for m in t.modules:
                if m.id == module_id:
                    return t, m
        return None


def _load_dir[T: BaseModel](directory: Path, model: type[T]) -> list[T]:
    items: list[T] = []
    for path in sorted(directory.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
            items.append(model.model_validate(data))
        except ValidationError as e:
            errs = "; ".join(f"{'.'.join(map(str, x['loc'])) or '<root>'}: {x['msg']}" for x in e.errors())
            raise ContentError(f"{path}: {errs}") from e
        except yaml.YAMLError as e:
            raise ContentError(f"{path}: invalid YAML: {e}") from e
    ids = [i.id for i in items]  # type: ignore[attr-defined]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ContentError(f"{directory}: duplicate ids {sorted(dupes)}")
    return items


def load(root: Path | None = None) -> Content:
    root = root or settings.content_dir
    c = Content(
        tracks=sorted(_load_dir(root / "tracks", Track), key=lambda t: (t.status != "available", t.phase, t.name)),
        projects=sorted(_load_dir(root / "projects", Project), key=lambda p: p.phase),
        challenges=_load_dir(root / "challenges", Challenge),
    )
    lessons = _load_dir(root / "lessons", Lesson) if (root / "lessons").exists() else []
    for lesson in lessons:
        if not c.module(lesson.id):
            raise ContentError(f"lesson {lesson.id} has no matching module in content/tracks")
        _check_lesson_yaml(lesson)
    c.lessons = {lesson.id: lesson for lesson in lessons}
    known = {ch.id for ch in c.challenges}
    for p in c.projects:
        unknown = set(p.challenges) - known
        if unknown:
            raise ContentError(f"project {p.id} references unknown challenges {sorted(unknown)}")
    return c


def _check_lesson_yaml(lesson: Lesson) -> None:
    """YAML in lessons must parse, and setup may only create namespaced objects of known kinds."""
    for ex in lesson.yaml:
        try:
            list(yaml.safe_load_all(ex.content))
        except yaml.YAMLError as e:
            raise ContentError(f"lesson {lesson.id}: YAML example '{ex.title}' is invalid: {e}") from e
    for exercise in lesson.exercises:
        if not exercise.setup:
            continue
        where = f"lesson {lesson.id} exercise {exercise.id}"
        try:
            docs = [d for d in yaml.safe_load_all(exercise.setup) if d]
        except yaml.YAMLError as e:
            raise ContentError(f"{where}: setup is invalid YAML: {e}") from e
        for d in docs:
            if not isinstance(d, dict) or d.get("kind") not in SETUP_KINDS:
                raise ContentError(f"{where}: setup kind must be one of {sorted(SETUP_KINDS)}")
            if (d.get("metadata") or {}).get("namespace"):
                raise ContentError(f"{where}: setup must not set a namespace (it always goes to lab-playground)")
            if (d["kind"], d["metadata"]["name"]) not in {(r.kind, r.name) for r in exercise.cleanup}:
                raise ContentError(f"{where}: {d['kind']} {d['metadata']['name']} from setup must be in cleanup")


_content: Content | None = None


def get_content() -> Content:
    global _content
    if _content is None:
        _content = load()
    return _content


def reload_content(root: Path | None = None) -> Content:
    global _content
    _content = load(root)
    return _content
