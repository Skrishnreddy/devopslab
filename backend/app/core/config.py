"""Application settings. Every value can be overridden with a DEVOPSLAB_* env var."""
from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVOPSLAB_", env_file=".env", extra="ignore")

    env: str = "development"
    data_dir: Path = Path.home() / ".devopslab"
    database_url: str | None = None
    content_dir: Path = REPO_ROOT / "content"

    # Loopback only: the API must never be reachable from the network.
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    session_hours: int = 12
    cookie_secure: bool = False  # True when served over HTTPS

    # Infrastructure (must match infra/config.env)
    colima_profile: str = "devopslab"
    cluster_name: str = "cloudmart"
    kubeconfig: Path = Path.home() / ".kube" / "devopslab"
    command_timeout_seconds: float = 5.0

    # Terminal sandboxes (docs/security/terminal.md)
    terminal_max_seconds: int = 4 * 3600  # hard limit per session (pod activeDeadlineSeconds)
    terminal_idle_seconds: int = 30 * 60  # closed after this long without input
    terminal_max_sessions: int = 4  # per user
    terminal_start_timeout_seconds: float = 90.0
    terminal_reap_interval_seconds: float = 60.0

    # AI Teacher (Phase 9). Local Ollama only until external providers exist.
    ai_enabled: bool = False
    ollama_url: str = "http://127.0.0.1:11434"

    @field_validator("ollama_url")
    @classmethod
    def _ollama_must_be_local(cls, v: str) -> str:
        if urlparse(v).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("ollama_url must point at this machine (127.0.0.1); external AI is opt-in only")
        return v.rstrip("/")

    @property
    def kube_context(self) -> str:
        return f"kind-{self.cluster_name}"

    @property
    def docker_context(self) -> str:
        return f"colima-{self.colima_profile}"

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'devopslab.db'}"

    @property
    def token_file(self) -> Path:
        return self.data_dir / "login-token"


settings = Settings()
