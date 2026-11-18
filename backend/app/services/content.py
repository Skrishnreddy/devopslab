"""Loads learning tracks and Engineer Mode projects from YAML in app/content."""
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import settings


@lru_cache
def tracks() -> list[dict]:
    return yaml.safe_load(Path(settings.content_dir, "tracks.yaml").read_text())["tracks"]


@lru_cache
def projects() -> list[dict]:
    return yaml.safe_load(Path(settings.content_dir, "projects.yaml").read_text())["projects"]


def find_module(module_id: str) -> tuple[dict, dict] | None:
    for t in tracks():
        for m in t.get("modules", []):
            if m["id"] == module_id:
                return t, m
    return None
