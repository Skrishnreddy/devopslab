"""Application settings. Every value can be overridden with a DEVOPSLAB_* env var."""
from pathlib import Path

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
