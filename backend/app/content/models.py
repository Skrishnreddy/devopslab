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


# ---- Lessons (Phase 5) ------------------------------------------------------
CheckKind = Literal["Pod", "Deployment", "ReplicaSet", "Service", "Endpoints", "ConfigMap"]
SETUP_KINDS = {"Pod", "Deployment", "ReplicaSet", "Service", "ConfigMap"}


class Check(Strict):
    """One automatic check, run read-only against the learner's namespace (lab-playground)."""

    type: Literal["exists", "absent", "field", "pods_ready", "rollout_ready", "endpoints", "answer"]
    description: str = Field(description="What the learner sees, e.g. 'Pod web is Running and Ready'")
    kind: CheckKind | None = None
    name: str | None = None
    selector: dict[str, str] = Field({}, description="Label selector (pods_ready)")
    path: str | None = Field(None, description="Dotted path into the object, e.g. spec.containers[0].image")
    equals: str | int | bool | None = None
    min: int | None = Field(None, ge=0, description="Minimum count (pods_ready, endpoints)")
    all_ready: bool = Field(False, description="pods_ready: every matching pod must be ready")
    source: Literal["node_count", "control_plane_node", "server_minor_version"] | None = Field(
        None, description="answer: the real cluster value the learner must find")
    key: str | None = Field(None, description="answer: ConfigMap key holding the learner's answer")

    @model_validator(mode="after")
    def _shape(self):
        need = {"exists": ["kind", "name"], "absent": ["kind", "name"], "field": ["kind", "name", "path"],
                "pods_ready": ["selector"], "rollout_ready": ["name"], "endpoints": ["name"],
                "answer": ["name", "source", "key"]}[self.type]
        missing = [f for f in need if not getattr(self, f)]
        if missing:
            raise ValueError(f"{self.type} check needs {', '.join(missing)}")
        if self.type == "field" and self.equals is None:
            raise ValueError("field check needs equals")
        return self


class ResourceRef(Strict):
    kind: CheckKind
    name: str


class Exercise(Strict):
    id: str = Slug
    title: str
    kind: Literal["practice", "troubleshooting"] = "practice"
    instructions: str
    expected_output: str | None = Field(None, description="What the learner should see when it works")
    setup: str | None = Field(None, description="Manifests applied to lab-playground first (troubleshooting)")
    checks: list[Check] = Field(min_length=1)
    cleanup: list[ResourceRef] = Field([], description="Objects deleted from lab-playground on reset")
    hint: str | None = None
    solution: str


class Command(Strict):
    command: str
    explanation: str


class YamlExample(Strict):
    title: str
    explanation: str
    content: str


class Question(Strict):
    question: str
    options: list[str] = Field(min_length=2, max_length=5)
    answer: int = Field(ge=0, description="Index of the correct option")
    explanation: str

    @model_validator(mode="after")
    def _answer_in_range(self):
        if self.answer >= len(self.options):
            raise ValueError("answer must index an option")
        return self


class Lesson(Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$", description="The module id this lesson belongs to")
    concept: str
    use_case: str
    architecture: str
    commands: list[Command] = Field(min_length=1)
    yaml: list[YamlExample] = []
    exercises: list[Exercise] = Field(min_length=1)
    quiz: list[Question] = Field(min_length=3)

    @model_validator(mode="after")
    def _complete(self):
        ids = [e.id for e in self.exercises]
        if len(ids) != len(set(ids)):
            raise ValueError("exercise ids must be unique within a lesson")
        if not any(e.kind == "troubleshooting" for e in self.exercises):
            raise ValueError("a lesson needs a troubleshooting exercise")
        return self


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
    lab: str | None = Field(None, description="Folder in labs/ with the project's known-good manifests")


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
