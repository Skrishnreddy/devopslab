"""Runs lab operations in the background and keeps the `labs` table honest.

One operation per lab at a time. Steps are kept in memory for the UI; the
status and the failing step's error are stored in the database, so a failure
is still visible after a restart. Expired labs are stopped (scaled to zero),
never deleted, so the learner's work survives.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ..core.config import REPO_ROOT, settings
from ..db.models import Activity, Lab
from ..db.session import get_db
from .labs import LabError, NamespaceLabProvisioner, Step

log = logging.getLogger("devopslab.labs")

# status while running -> status after success
TRANSITIONS = {
    "deploy": ("deploying", "running"),
    "start": ("starting", "running"),
    "stop": ("stopping", "stopped"),
    "reset": ("resetting", "running"),
    "delete": ("deleting", None),  # row removed
}
BUSY = {s for s, _ in TRANSITIONS.values()}
ALLOWED = {  # action -> statuses it may start from (None = no lab yet)
    "deploy": {None},
    "start": {"stopped", "failed"},
    "stop": {"running", "failed"},
    "reset": {"running", "stopped", "failed"},
    "delete": {"running", "stopped", "failed"},
}


@dataclass
class Operation:
    action: str
    steps: list[Step] = field(default_factory=list)
    state: str = "running"  # running | succeeded | failed
    error: str | None = None
    failed_step: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def view(self) -> dict:
        return {"action": self.action, "state": self.state, "error": self.error, "failed_step": self.failed_step,
                "started_at": self.started_at, "finished_at": self.finished_at,
                "steps": [s.view() for s in self.steps]}


class LabConflict(Exception):
    pass


class LabService:
    def __init__(self, provisioner: NamespaceLabProvisioner | None = None):
        self.provisioner = provisioner or NamespaceLabProvisioner(REPO_ROOT / "labs")
        self.ops: dict[str, Operation] = {}
        self._tasks: set[asyncio.Task] = set()

    @staticmethod
    def lab_id(ref_id: str) -> str:
        return ref_id  # single user today; a hosted version prefixes the user (docs/security/lab-isolation.md)

    def view(self, lab: Lab | None, ref_id: str) -> dict:
        lab_id = self.lab_id(ref_id)
        op = self.ops.get(lab_id)
        spec = self.provisioner.spec(ref_id)
        base = {"id": lab_id, "kind": "project", "ref_id": ref_id, "url": spec.url,
                "operation": op.view() if op else None}
        if lab is None:
            return base | {"status": "not_deployed", "namespaces": [], "last_error": None,
                           "created_at": None, "updated_at": None, "expires_at": None}
        return base | {"status": lab.status, "namespaces": lab.namespaces, "last_error": lab.last_error,
                       "created_at": lab.created_at, "updated_at": lab.updated_at, "expires_at": lab.expires_at}

    def start_operation(self, db, user_id: int, ref_id: str, action: str, *, reason: str = "") -> Operation:
        self.provisioner.source_dir(ref_id)  # validates the id and that the lab exists
        lab_id = self.lab_id(ref_id)
        lab = db.get(Lab, lab_id)
        if lab is not None and lab.user_id != user_id:
            raise LabConflict("This lab belongs to another user")
        current = lab.status if lab else None
        if action not in ALLOWED:
            raise LabConflict(f"Unknown action {action}")
        if current in BUSY:
            raise LabConflict(f"The lab is busy ({current}). Wait for it to finish.")
        if current not in ALLOWED[action]:
            raise LabConflict(f"Can't {action} a lab that is {current or 'not deployed'}")
        running_status, _ = TRANSITIONS[action]
        now = datetime.now(UTC)
        if lab is None:
            lab = Lab(id=lab_id, user_id=user_id, kind="project", ref_id=ref_id, status=running_status,
                      namespaces=[])
            db.add(lab)
        lab.status, lab.last_error, lab.updated_at = running_status, None, now
        db.add(Activity(user_id=user_id, kind="project", ref_id=ref_id,
                        title=f"{ref_id}: {action}{f' ({reason})' if reason else ''}"))
        db.commit()
        op = Operation(action)
        self.ops[lab_id] = op
        task = asyncio.create_task(self._run(lab_id, ref_id, op))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return op

    async def _run(self, lab_id: str, ref_id: str, op: Operation) -> None:
        def on_step(steps: list[Step]) -> None:
            op.steps = list(steps)

        try:
            await asyncio.to_thread(self.provisioner.run, op.action, ref_id, on_step)
            op.state = "succeeded"
        except LabError as e:
            op.state, op.error, op.failed_step = "failed", str(e), e.step
        except Exception as e:  # never leave a lab stuck in a busy state
            op.state, op.error, op.failed_step = "failed", f"{e.__class__.__name__}: {e}", "unexpected error"
        finally:
            op.finished_at = time.time()
            self._record(lab_id, ref_id, op)

    def _record(self, lab_id: str, ref_id: str, op: Operation) -> None:
        db = next(get_db())
        try:
            lab = db.get(Lab, lab_id)
            if lab is None:
                return
            now = datetime.now(UTC)
            _, done_status = TRANSITIONS[op.action]
            if op.state == "succeeded" and done_status is None:
                db.delete(lab)
            elif op.state == "succeeded":
                lab.status, lab.last_error = done_status, None
                if op.action != "stop":
                    lab.namespaces = self.provisioner.namespaces(ref_id)
                lab.expires_at = now + timedelta(seconds=settings.lab_idle_seconds) if done_status == "running" \
                    else None
            else:
                lab.status = "failed"
                lab.last_error = f"{op.failed_step}: {op.error}"[:4000]
                created = any(s.name == "create namespaces" and s.state == "ok" for s in op.steps)
                if created and not lab.namespaces:  # a failed deploy still left namespaces running
                    try:
                        lab.namespaces = self.provisioner.namespaces(ref_id)
                    except LabError as e:
                        log.warning("lab %s: couldn't list namespaces after failure: %s", lab_id, e)
            lab.updated_at = now
            db.commit()
            log.info("lab %s %s: %s%s", lab_id, op.action, op.state, f" at '{op.failed_step}'" if op.error else "")
        finally:
            db.close()

    def extend(self, db, lab: Lab) -> Lab:
        lab.expires_at = datetime.now(UTC) + timedelta(seconds=settings.lab_idle_seconds)
        db.commit()
        return lab

    async def expire(self) -> list[str]:
        """Stop running labs whose time is up. Called by the background reaper."""
        db = next(get_db())
        stopped = []
        try:
            now = datetime.now(UTC)
            for lab in db.scalars(select(Lab).where(Lab.status == "running", Lab.expires_at.is_not(None))):
                if lab.expires_at <= now:
                    self.start_operation(db, lab.user_id, lab.ref_id, "stop", reason="time limit reached")
                    stopped.append(lab.id)
        finally:
            db.close()
        return stopped

    def recover(self) -> None:
        """After a restart, labs caught mid-operation are marked failed with the reason."""
        db = next(get_db())
        try:
            for lab in db.scalars(select(Lab).where(Lab.status.in_(BUSY))):
                lab.status = "failed"
                lab.last_error = "interrupted: DevOpsLab restarted during the operation. Reset the lab to repair it."
            db.commit()
        finally:
            db.close()
