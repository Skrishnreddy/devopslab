import pytest
from fastapi.testclient import TestClient

from app.content import loader
from app.core.config import settings
from app.db import session as dbsession

ORIGIN = "http://127.0.0.1:5173"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own data dir, database and no kubeconfig."""
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "kubeconfig", tmp_path / "no-kubeconfig")
    dbsession.reset_engine()
    loader._content = None
    yield
    dbsession.reset_engine()


@pytest.fixture(autouse=True)
def fake_terminals(monkeypatch):
    """No test talks to a real cluster: terminals use an in-memory pod backend."""
    from app.providers import registry
    from app.providers.terminal import TerminalManager
    from tests.terminal_fakes import FakeBackend

    backend = FakeBackend()
    mgr = TerminalManager(backend)
    monkeypatch.setattr(registry, "terminal", lambda: mgr)
    return mgr


@pytest.fixture()
def client():
    from app.main import create_app
    with TestClient(create_app(), base_url="http://127.0.0.1:8000", headers={"Origin": ORIGIN}) as c:
        yield c


@pytest.fixture()
def authed(client):
    token = settings.token_file.read_text().strip()
    assert client.post("/api/v1/auth/login", json={"token": token}).status_code == 204
    return client
