import stat
from datetime import UTC, datetime, timedelta

from fastapi.routing import APIRoute

from app.core.config import settings
from app.db import session as dbsession
from app.db.models import Session

PUBLIC = {"/api/v1/health", "/api/v1/auth/login"}


def test_every_api_route_requires_a_session(client):
    routes = [r for r in client.app.routes if isinstance(r, APIRoute) and r.path.startswith("/api/v1")]
    assert len(routes) > 10
    for r in routes:
        if r.path in PUBLIC:
            continue
        method = sorted(r.methods)[0]
        path = r.path.replace("{track_id}", "kubernetes").replace("{module_id}", "x")
        res = client.request(method, path, json={})
        assert res.status_code == 401, f"{method} {r.path} -> {res.status_code}"
        assert res.json()["error"]["code"] == "unauthorized"


def test_token_file_is_private_and_stable_across_restarts(client):
    f = settings.token_file
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    first = f.read_text()
    from fastapi.testclient import TestClient

    from app.main import create_app
    with TestClient(create_app()):
        pass
    assert f.read_text() == first


def test_bad_token_rejected(client):
    r = client.post("/api/v1/auth/login", json={"token": "nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"


def test_login_from_foreign_origin_rejected(client):
    token = settings.token_file.read_text().strip()
    r = client.post("/api/v1/auth/login", json={"token": token}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_login_sets_strict_httponly_cookie_and_me_works(client):
    token = settings.token_file.read_text().strip()
    r = client.post("/api/v1/auth/login", json={"token": token})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    me = client.get("/api/v1/auth/me").json()
    assert me["username"] == "admin" and me["role"] == "admin"


def test_writes_need_allowed_origin(authed):
    r = authed.put("/api/v1/learn/modules/k8s-01-architecture/progress", json={"status": "completed"},
                   headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "bad_origin"


def test_logout_ends_session(authed):
    assert authed.post("/api/v1/auth/logout").status_code == 204
    assert authed.get("/api/v1/auth/me").status_code == 401


def test_expired_session_rejected(authed):
    db = next(dbsession.get_db())
    for s in db.query(Session).all():
        s.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    db.close()
    r = authed.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "session_expired"
