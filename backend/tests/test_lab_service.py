"""Lab lifecycle through the API, with the kubectl work replaced by a fake provisioner."""
import asyncio
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import REPO_ROOT
from app.db.models import Lab, User
from app.db.session import get_db
from app.providers import registry
from app.providers.lab_service import LabService
from app.providers.labs import LabError, NamespaceLabProvisioner, Step


class FakeProvisioner(NamespaceLabProvisioner):
    def __init__(self):
        super().__init__(REPO_ROOT / "labs")
        self.actions, self.fail, self.gate = [], {}, threading.Event()
        self.gate.set()

    def namespaces(self, source, docs=None):
        return ["lab-cloudmart"]

    def run(self, action, source, on_step=None):
        self.actions.append(action)
        steps = [Step("render manifests", "ok"), Step(f"{action} step", "running")]
        if on_step:
            on_step(steps)
        assert self.gate.wait(5)
        if action in self.fail:
            steps[1].state = "failed"
            raise LabError(self.fail[action], "wait until ready")
        steps[1].state = "ok"
        if on_step:
            on_step(steps)
        return steps


@pytest.fixture()
def prov(monkeypatch):
    p = FakeProvisioner()
    svc = LabService(p)
    monkeypatch.setattr(registry, "labs", lambda: svc)
    return p


def settle(authed, lab_id="cloudmart"):
    for _ in range(200):
        lab = authed.get(f"/api/v1/labs/{lab_id}").json()
        if not lab["operation"] or lab["operation"]["state"] != "running":
            return lab
        time.sleep(0.01)
    raise AssertionError("operation never finished")


def test_deploy_then_running_with_expiry(authed, prov):
    r = authed.post("/api/v1/labs", json={"ref_id": "cloudmart"})
    assert r.status_code == 202 and r.json()["status"] == "deploying"
    lab = settle(authed)
    assert lab["status"] == "running" and lab["namespaces"] == ["lab-cloudmart"]
    assert lab["url"] == "http://localhost:8080" and lab["expires_at"]
    assert [s["state"] for s in lab["operation"]["steps"]] == ["ok", "ok"]
    assert authed.post("/api/v1/labs", json={"ref_id": "cloudmart"}).status_code == 409  # already deployed


def test_busy_lab_rejects_a_second_operation(authed, prov):
    prov.gate.clear()
    assert authed.post("/api/v1/labs", json={"ref_id": "cloudmart"}).status_code == 202
    r = authed.post("/api/v1/labs/cloudmart/reset")
    assert r.status_code == 409 and "busy" in r.json()["error"]["message"]
    prov.gate.set()
    assert settle(authed)["status"] == "running"


def test_failed_reset_reports_the_step_and_error(authed, prov):
    authed.post("/api/v1/labs", json={"ref_id": "cloudmart"})
    settle(authed)
    prov.fail["reset"] = "deployment.apps/api isn't ready: ErrImageNeverPull"
    assert authed.post("/api/v1/labs/cloudmart/reset").status_code == 202
    lab = settle(authed)
    assert lab["status"] == "failed"
    assert lab["last_error"] == "wait until ready: deployment.apps/api isn't ready: ErrImageNeverPull"
    assert lab["operation"]["failed_step"] == "wait until ready"
    assert lab["operation"]["steps"][1]["state"] == "failed"
    # a failed lab can be reset again, and success clears the error
    prov.fail.clear()
    authed.post("/api/v1/labs/cloudmart/reset")
    lab = settle(authed)
    assert lab["status"] == "running" and lab["last_error"] is None


def test_stop_start_delete_lifecycle(authed, prov):
    authed.post("/api/v1/labs", json={"ref_id": "cloudmart"})
    settle(authed)
    authed.post("/api/v1/labs/cloudmart/stop")
    lab = settle(authed)
    assert lab["status"] == "stopped" and lab["expires_at"] is None
    assert authed.post("/api/v1/labs/cloudmart/stop").status_code == 409
    assert authed.post("/api/v1/labs/cloudmart/extend").status_code == 409
    authed.post("/api/v1/labs/cloudmart/start")
    assert settle(authed)["status"] == "running"
    assert authed.post("/api/v1/labs/cloudmart/extend").status_code == 202
    assert authed.delete("/api/v1/labs/cloudmart").status_code == 202
    assert settle(authed)["status"] == "not_deployed"
    assert prov.actions == ["deploy", "stop", "start", "delete"]


def test_unknown_labs_and_actions(authed, prov):
    assert authed.post("/api/v1/labs", json={"ref_id": "kube-system"}).status_code == 404
    assert authed.post("/api/v1/labs", json={"ref_id": "../etc"}).status_code == 422
    assert authed.post("/api/v1/labs/cloudmart/format").status_code == 404
    assert authed.post("/api/v1/labs/cloudmart/start").status_code == 409  # not deployed
    assert authed.get("/api/v1/labs/cloudmart/usage").status_code == 404
    assert prov.actions == []


def test_labs_need_a_session(client, prov):
    assert client.get("/api/v1/labs").status_code == 401
    assert client.post("/api/v1/labs", json={"ref_id": "cloudmart"}).status_code == 401


def test_another_users_lab_is_off_limits(authed, prov):
    db = next(get_db())
    db.add(User(id=999, username="someone-else"))
    db.flush()
    db.add(Lab(id="cloudmart", user_id=999, kind="project", ref_id="cloudmart", status="running", namespaces=[]))
    db.commit()
    db.close()
    assert authed.post("/api/v1/labs/cloudmart/reset").status_code == 409
    assert authed.get("/api/v1/labs/cloudmart").json()["status"] == "not_deployed"
    assert prov.actions == []


def test_expiry_stops_but_never_deletes(authed, prov):
    asyncio.run(_expire())
    assert prov.actions == ["stop"]


async def _expire():
    svc = registry.labs()
    db = next(get_db())
    db.add(Lab(id="cloudmart", user_id=1, kind="project", ref_id="cloudmart", status="running",
               namespaces=["lab-cloudmart"], expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    db.commit()
    db.close()
    assert await svc.expire() == ["cloudmart"]
    for _ in range(200):
        if svc.ops["cloudmart"].state != "running":
            break
        await asyncio.sleep(0.01)
    db = next(get_db())
    assert db.get(Lab, "cloudmart").status == "stopped"
    db.close()


def test_recover_marks_interrupted_labs_failed(authed, prov):
    db = next(get_db())
    db.add(Lab(id="cloudmart", user_id=1, kind="project", ref_id="cloudmart", status="resetting", namespaces=[]))
    db.commit()
    db.close()
    registry.labs().recover()
    db = next(get_db())
    lab = db.get(Lab, "cloudmart")
    assert lab.status == "failed" and lab.last_error.startswith("interrupted")
    db.close()
