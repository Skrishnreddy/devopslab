"""Exercise setup and reset. Writes only to lab-playground, only the objects the lesson names."""
from __future__ import annotations

from collections.abc import Callable

import yaml

from ..content.models import Exercise
from ..providers.labs import kubectl
from .checks import NAMESPACE

Kubectl = Callable[..., str]


def setup(exercise: Exercise, run: Kubectl = kubectl) -> list[str]:
    """Apply the exercise's starting state (the broken app for troubleshooting)."""
    if not exercise.setup:
        return []
    docs = [d for d in yaml.safe_load_all(exercise.setup) if d]
    for d in docs:
        meta = d.setdefault("metadata", {})
        meta["namespace"] = NAMESPACE
        meta.setdefault("labels", {})["devopslab.io/exercise"] = exercise.id
    out = run("apply", "-n", NAMESPACE, "-f", "-", stdin=yaml.safe_dump_all(docs), step="set up", timeout=60)
    return out.strip().splitlines()


def reset(exercise: Exercise, run: Kubectl = kubectl) -> list[str]:
    """Delete what the exercise creates, then apply its starting state again."""
    done = []
    for ref in exercise.cleanup:
        run("delete", f"{ref.kind.lower()}/{ref.name}", "-n", NAMESPACE, "--ignore-not-found", "--wait=true",
            "--timeout=60s", step="clean up", timeout=80)
        done.append(f"deleted {ref.kind} {ref.name} (if it existed)")
    return done + setup(exercise, run)
