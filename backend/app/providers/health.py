"""Shared shape for infrastructure checks."""
from typing import Literal

from pydantic import BaseModel

Status = Literal["ok", "warning", "error", "missing"]
SEVERITY: dict[str, int] = {"ok": 0, "warning": 1, "missing": 2, "error": 3}


class ComponentHealth(BaseModel):
    id: str
    name: str
    status: Status
    version: str | None = None
    message: str
    remediation: str | None = None
    details: dict[str, str | int | float] = {}
    optional: bool = False  # optional components never affect the overall status


def worst(statuses: list[str]) -> str:
    return max(statuses, key=lambda s: SEVERITY[s]) if statuses else "ok"
