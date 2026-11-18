import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "kubeconfig", str(tmp_path / "missing-kubeconfig"))
    monkeypatch.setattr(settings, "labs_dir", str(tmp_path / "labs"))
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_cluster_down_is_graceful(client):
    body = client.get("/api/cluster/summary").json()
    assert body["connected"] is False
    assert "make up" in body["reason"]
    assert client.get("/api/cluster/pods").status_code == 503


def test_kubernetes_track_has_20_modules(client):
    tracks = client.get("/api/learn/tracks").json()
    k8s = next(t for t in tracks if t["id"] == "kubernetes")
    assert len(k8s["modules"]) == 20
    assert k8s["progress"]["percent"] == 0


def test_progress_round_trip(client):
    for mid in ("k8s-01", "k8s-02", "k8s-03", "k8s-04", "k8s-05"):
        assert client.post(f"/api/learn/modules/{mid}/complete", json={"completed": True}).status_code == 200
    k8s = client.get("/api/learn/tracks/kubernetes").json()
    assert k8s["progress"] == {"completed": 5, "total": 20, "percent": 25}
    client.post("/api/learn/modules/k8s-05/complete", json={"completed": False})
    assert client.get("/api/learn/tracks/kubernetes").json()["progress"]["completed"] == 4


def test_unknown_module_404(client):
    assert client.post("/api/learn/modules/nope/complete", json={}).status_code == 404


def test_projects_listed(client):
    ids = [p["id"] for p in client.get("/api/engineer/projects").json()]
    assert ids[0] == "cloudmart" and len(ids) == 5


@pytest.mark.parametrize("lab", ["cloudmart", "../etc", "UPPER", "a" * 60])
def test_reset_refuses_unknown_or_unsafe_labs(client, lab):
    r = client.post(f"/api/engineer/labs/{lab}/reset")
    assert r.status_code in (404, 409)
