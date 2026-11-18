"""Terminal sandbox: pod hardening, session API, WebSocket auth and the reaper."""
import asyncio
import json
from pathlib import Path

import pytest
import yaml
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.db.models import TerminalSession
from app.db.session import get_db
from app.providers.terminal import TerminalError, TerminalManager, build_pod
from tests.conftest import ORIGIN
from tests.terminal_fakes import FakeBackend

REPO = Path(__file__).resolve().parents[2]
WS = "ws://127.0.0.1:8000/api/v1/terminal/sessions/{}/stream"  # cookies are scoped to 127.0.0.1


# ---------------------------------------------------------------- pod spec
@pytest.mark.parametrize("profile", ["linux", "kubernetes"])
def test_pod_is_hardened(profile):
    pod = build_pod("t-0123456789abcdef", 1, profile)
    spec = pod["spec"]
    c = spec["containers"][0]
    assert pod["metadata"]["namespace"] == "devopslab-terminal"
    assert spec["securityContext"]["runAsNonRoot"] is True
    assert spec["securityContext"]["runAsUser"] == 1000
    assert spec["securityContext"]["seccompProfile"] == {"type": "RuntimeDefault"}
    assert c["securityContext"] == {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                    "privileged": False, "capabilities": {"drop": ["ALL"]}}
    assert c["resources"]["limits"] == {"cpu": "500m", "memory": "512Mi", "ephemeral-storage": "1Gi"}
    assert spec["activeDeadlineSeconds"] == settings.terminal_max_seconds
    assert not spec.get("hostNetwork") and not spec.get("hostPID") and not spec.get("hostIPC")
    for v in spec["volumes"]:  # no hostPath, so no Docker socket or host files
        assert set(v) & {"hostPath"} == set()
        assert "emptyDir" in v or "configMap" in v


def test_linux_pod_has_no_cluster_credentials():
    spec = build_pod("t-0123456789abcdef", 1, "linux")["spec"]
    assert spec["automountServiceAccountToken"] is False
    assert spec["serviceAccountName"] == "default"
    assert all(e["name"] != "KUBECONFIG" for e in spec["containers"][0]["env"])


def test_kubernetes_pod_uses_scoped_service_account():
    spec = build_pod("t-0123456789abcdef", 1, "kubernetes")["spec"]
    assert spec["serviceAccountName"] == "lab-learner"
    assert spec["automountServiceAccountToken"] is True


def test_docker_profile_is_not_available_yet():
    with pytest.raises(TerminalError) as e:
        build_pod("t-0123456789abcdef", 1, "docker")
    assert e.value.code == "unsupported_profile"


# ---------------------------------------------------------------- manifests
def _docs(path: str) -> list[dict]:
    return [d for d in yaml.safe_load_all((REPO / path).read_text()) if d]


def test_learner_rbac_never_grants_cluster_admin():
    for d in _docs("infra/manifests/terminal/rbac.yaml"):
        if d["kind"] in {"RoleBinding", "ClusterRoleBinding"}:
            assert d["roleRef"]["name"] not in {"cluster-admin", "admin"}
            if d["kind"] == "RoleBinding":
                assert d["metadata"]["namespace"].startswith("lab-")
        if d["kind"] == "ClusterRole":
            for rule in d["rules"]:
                assert rule["verbs"] and set(rule["verbs"]) <= {"get", "list", "watch"}
                assert "secrets" not in rule.get("resources", [])
                assert "*" not in rule.get("resources", []) and "*" not in rule["verbs"]
        if d["kind"] == "ServiceAccount":
            assert d.get("automountServiceAccountToken") is False


def test_terminal_namespace_is_default_deny():
    docs = _docs("infra/manifests/terminal/networkpolicy.yaml")
    deny = next(d for d in docs if d["metadata"]["name"] == "default-deny")
    assert deny["spec"]["podSelector"] == {}
    assert set(deny["spec"]["policyTypes"]) == {"Ingress", "Egress"}
    assert "ingress" not in deny["spec"] and "egress" not in deny["spec"]
    for d in docs:
        assert "ingress" not in d["spec"], "nothing may connect into a terminal pod"


def test_terminal_namespace_enforces_restricted_pod_security():
    ns = next(d for d in _docs("infra/manifests/base/namespaces.yaml")
              if d["metadata"]["name"] == "devopslab-terminal")
    assert ns["metadata"]["labels"]["pod-security.kubernetes.io/enforce"] == "restricted"


# ---------------------------------------------------------------- manager
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_reaper_closes_idle_and_overage_sessions():
    clock = Clock()
    backend = FakeBackend()
    mgr = TerminalManager(backend, clock=clock)
    closed_log = []
    mgr.on_close = lambda sid, reason: closed_log.append((sid, reason))

    async def run():
        idle = await mgr.open(1, "linux")
        busy = await mgr.open(1, "linux")
        clock.t += settings.terminal_idle_seconds - 1
        mgr.touch(busy)
        assert await mgr.reap() == []
        clock.t += 2
        assert await mgr.reap() == [idle.id]
        clock.t += settings.terminal_max_seconds
        mgr.touch(busy)
        assert await mgr.reap() == [busy.id]
        return idle, busy

    idle, busy = asyncio.run(run())
    assert backend.pods == {}
    assert [r for _, r in closed_log] == ["Closed after being idle", "Session reached its maximum length"]


def test_failed_start_deletes_the_pod_and_reports_why():
    backend = FakeBackend(fail_ready=TerminalError("pod_failed", "Sandbox pod failed: ErrImageNeverPull"))
    mgr = TerminalManager(backend)
    with pytest.raises(TerminalError, match="ErrImageNeverPull"):
        asyncio.run(mgr.open(1, "linux"))
    assert backend.pods == {} and len(backend.deleted) == 1
    assert mgr.for_user(1) == []


def test_orphan_pods_are_deleted():
    backend = FakeBackend()
    backend.extra_sessions = ["t-aaaaaaaaaaaaaaaa"]
    mgr = TerminalManager(backend)

    async def run():
        kept = await mgr.open(1, "linux")
        assert await mgr.reap_orphans() == 1
        return kept

    kept = asyncio.run(run())
    assert backend.deleted == ["term-aaaaaaaaaaaaaaaa"]
    assert kept.pod in backend.pods


# ---------------------------------------------------------------- REST API
def test_terminal_api_requires_login(client):
    assert client.get("/api/v1/terminal/sessions").status_code == 401
    assert client.post("/api/v1/terminal/sessions", json={"profile": "linux"}).status_code == 401


def test_profiles_mark_docker_planned(authed):
    profiles = {p["id"]: p for p in authed.get("/api/v1/terminal/profiles").json()}
    assert profiles["linux"]["available"] and profiles["kubernetes"]["available"]
    assert profiles["docker"]["available"] is False


def test_open_list_close_session(authed, fake_terminals):
    r = authed.post("/api/v1/terminal/sessions", json={"profile": "kubernetes"})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["status"] == "ready" and s["profile"] == "kubernetes"
    assert [x["id"] for x in authed.get("/api/v1/terminal/sessions").json()] == [s["id"]]
    assert authed.delete(f"/api/v1/terminal/sessions/{s['id']}").status_code == 204
    assert authed.get("/api/v1/terminal/sessions").json() == []
    assert fake_terminals.backend.pods == {}
    db = next(get_db())
    row = db.get(TerminalSession, s["id"])
    assert row.closed_at is not None and row.close_reason == "Closed by you"
    db.close()


def test_docker_profile_rejected(authed):
    r = authed.post("/api/v1/terminal/sessions", json={"profile": "docker"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "unsupported_profile"


def test_session_limit(authed, monkeypatch):
    monkeypatch.setattr(settings, "terminal_max_sessions", 2)
    for _ in range(2):
        assert authed.post("/api/v1/terminal/sessions", json={"profile": "linux"}).status_code == 201
    r = authed.post("/api/v1/terminal/sessions", json={"profile": "linux"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_many_sessions"


def test_cannot_touch_another_users_session(authed, fake_terminals):
    async def other_user():
        return await fake_terminals.open(999, "linux")

    other = asyncio.run(other_user())
    assert authed.delete(f"/api/v1/terminal/sessions/{other.id}").status_code == 404
    assert authed.get("/api/v1/terminal/sessions").json() == []
    with pytest.raises(WebSocketDisconnect) as e, \
            authed.websocket_connect(WS.format(other.id),
                                     headers={"Origin": ORIGIN}) as ws:
        ws.receive_text()
    assert e.value.code == 4404


def test_write_needs_allowed_origin(authed):
    r = authed.post("/api/v1/terminal/sessions", json={"profile": "linux"},
                    headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


# ---------------------------------------------------------------- WebSocket
def _open(authed) -> str:
    return authed.post("/api/v1/terminal/sessions", json={"profile": "linux"}).json()["id"]


def test_websocket_rejects_foreign_origin(authed):
    sid = _open(authed)
    with pytest.raises(WebSocketDisconnect) as e, \
            authed.websocket_connect(WS.format(sid),
                                     headers={"Origin": "http://evil.example"}) as ws:
        ws.receive_text()
    assert e.value.code == 4403


def test_websocket_rejects_missing_login(client, authed):
    sid = _open(authed)
    client.cookies.clear()
    with pytest.raises(WebSocketDisconnect) as e, \
            client.websocket_connect(WS.format(sid),
                                     headers={"Origin": ORIGIN}) as ws:
        ws.receive_text()
    assert e.value.code == 4401


def test_websocket_bridges_input_output_and_resize(authed, fake_terminals):
    sid = _open(authed)
    with authed.websocket_connect(WS.format(sid), headers={"Origin": ORIGIN}) as ws:
        assert json.loads(ws.receive_text()) == {"type": "status", "state": "connected"}
        ws.send_text(json.dumps({"type": "resize", "cols": 120, "rows": 40}))
        ws.send_text(json.dumps({"type": "input", "data": "ls\r"}))
        assert ws.receive_bytes() == b"echo:ls\r"
        ws.send_text(json.dumps({"type": "resize", "cols": 99999, "rows": 1}))  # ignored
        ws.send_text("not json")  # ignored
        ws.send_text(json.dumps({"type": "input", "data": "x"}))
        assert ws.receive_bytes() == b"echo:x"
    stream = fake_terminals.backend.streams[0]
    assert stream.resizes == [(120, 40)]
    assert stream.written == [b"ls\r", b"x"]
    # Closing the tab detaches; the sandbox stays until it's closed or reaped.
    assert fake_terminals.get(sid, 1).status == "ready"


def test_websocket_reports_when_shell_exits(authed, fake_terminals):
    sid = _open(authed)
    with authed.websocket_connect(WS.format(sid), headers={"Origin": ORIGIN}) as ws:
        ws.receive_text()
        fake_terminals.backend.streams[0].feed(None)
        msg = json.loads(ws.receive_text())
    assert msg["state"] == "closed" and "exited" in msg["reason"]
