from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVOPSLAB_", env_file=".env")

    # Backend listens on loopback only; it must never be reachable from the network.
    host: str = "127.0.0.1"
    port: int = 8000
    kube_context: str = "kind-cloudmart"
    kubeconfig: str = str(Path.home() / ".kube" / "devopslab")
    db_path: str = str(ROOT / "backend" / "devopslab.db")
    content_dir: str = str(Path(__file__).parent / "content")
    labs_dir: str = str(ROOT / "labs")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
