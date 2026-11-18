"""Content schemas. JSON Schemas in content/schemas/ are generated from these
models (`make schemas`), so contributors and the backend share one definition."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Slug = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
Level = Literal["beginner", "intermediate", "advanced"]
Status = Literal["available", "planned"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Module(Strict):
    id: str = Slug
    order: int = Field(ge=1)
    title: str
    level: Level
    task: str = Field(description="The practical task the learner performs")
    skills: list[str] = []
    phase: int = Field(5, description="Build phase that delivers the full lesson")


class Track(Strict):
    id: str = Slug
    name: str
    description: str
    status: Status
    phase: int
    modules: list[Module] = []

    @model_validator(mode="after")
    def _unique_modules(self):
        ids = [m.id for m in self.modules]
        if len(ids) != len(set(ids)):
            raise ValueError("module ids must be unique within a track")
        return self


class Project(Strict):
    id: str = Slug
    name: str
    status: Status
    phase: int
    summary: str
    components: list[str]
    topics: list[str]
    challenges: list[str] = Field([], description="Challenge ids that run against this project")


class Hint(Strict):
    level: Literal[1, 2, 3]
    kind: Literal["direction", "resource", "approach"]
    text: str


class Step(Strict):
    """One declarative action the engine performs (Phase 6)."""

    action: Literal["apply", "patch", "delete", "scale", "exec", "wait"]
    target: dict[str, str] = {}
    manifest: str | None = None
    patch: str | None = None
    patch_type: Literal["json", "merge", "strategic"] | None = None
    condition: str | None = None
    timeout_seconds: int = 120


class Validation(Strict):
    check: Literal["rollout_ready", "pod_ready", "http", "endpoints_exist", "resource_field", "command"]
    target: dict[str, str] = {}
    expect: dict[str, str | int | bool] = {}
    description: str


class Challenge(Strict):
    id: str = Slug
    name: str
    difficulty: Level
    technology: Literal["kubernetes", "docker", "linux", "terraform", "jenkins", "ansible", "security"]
    status: Status
    phase: int = 6
    description: str
    skills: list[str] = []
    initial_state: dict[str, str] | None = Field(None, description="Lab source + namespace the scenario starts from")
    inject: list[Step] = []
    symptoms: list[str] = []
    hints: list[Hint] = []
    validation: list[Validation] = []
    root_cause: str | None = None
    resolution: str | None = None
    reset: dict[str, str] | None = None

    @model_validator(mode="after")
    def _complete_when_available(self):
        if self.hints and [h.level for h in self.hints] != [1, 2, 3]:
            raise ValueError("hints must be exactly levels 1, 2, 3 in order")
        if self.status == "available":
            missing = [f for f in ("initial_state", "inject", "symptoms", "hints", "validation",
                                   "root_cause", "resolution", "reset") if not getattr(self, f)]
            if missing:
                raise ValueError(f"available challenge is missing: {', '.join(missing)}")
        return self
