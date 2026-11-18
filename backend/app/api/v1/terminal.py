"""Terminal sessions: REST for lifecycle, one WebSocket per attached browser tab.

WebSocket protocol (docs/api.md):
  client -> server  text  {"type": "input", "data": "..."} | {"type": "resize", "cols": n, "rows": n}
  server -> client  binary  terminal output bytes
                    text    {"type": "status", "state": "connected"|"closed", "reason": "..."}
"""
import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session as DB

from ...auth.deps import COOKIE, Principal, current_principal, principal_from_cookie
from ...core.config import settings
from ...core.errors import AppError
from ...db.models import TerminalSession
from ...db.session import get_db
from ...providers import registry
from ...providers.terminal import SUPPORTED, Profile, TerminalError

log = logging.getLogger("devopslab.terminal")
router = APIRouter(prefix="/terminal", tags=["terminal"])

PROFILES = [
    {"id": "linux", "name": "Linux", "available": True,
     "description": "Ubuntu shell with common tools. No cluster access."},
    {"id": "kubernetes", "name": "Kubernetes", "available": True,
     "description": "kubectl and helm, scoped to the lab-playground namespace. Read-only elsewhere."},
    {"id": "docker", "name": "Docker", "available": False, "phase": 2,
     "description": "Planned: needs an isolated Docker engine per session."},
]


class OpenBody(BaseModel):
    profile: Profile


def _err(e: TerminalError) -> AppError:
    return AppError(e.status, e.code, e.message)


def record_close(sid: str, reason: str) -> None:
    """TerminalManager.on_close hook: complete the audit row (reaper, user, shutdown)."""
    db = next(get_db())
    try:
        row = db.get(TerminalSession, sid)
        if row and row.closed_at is None:
            row.closed_at, row.close_reason = datetime.now(UTC), reason[:256]
            db.commit()
    finally:
        db.close()


@router.get("/profiles")
def profiles(_: Principal = Depends(current_principal)):
    return PROFILES


@router.get("/sessions")
def list_sessions(p: Principal = Depends(current_principal)):
    return [s.view() for s in registry.terminal().for_user(p.user.id)]


@router.post("/sessions", status_code=201)
async def open_session(body: OpenBody, p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    if body.profile not in SUPPORTED:
        raise AppError(400, "unsupported_profile", f"The {body.profile} terminal is planned, not available yet")
    mgr = registry.terminal()
    try:
        s = await mgr.open(p.user.id, body.profile)
    except TerminalError as e:
        raise _err(e) from e
    db.add(TerminalSession(id=s.id, user_id=p.user.id, profile=s.profile, pod=s.pod))
    db.commit()
    return s.view()


@router.delete("/sessions/{sid}", status_code=204)
async def close_session(sid: str, p: Principal = Depends(current_principal)):
    mgr = registry.terminal()
    try:
        s = mgr.get(sid, p.user.id)
    except TerminalError as e:
        raise _err(e) from e
    await mgr.close(s, "Closed by you")


@router.websocket("/sessions/{sid}/stream")
async def stream(ws: WebSocket, sid: str):
    # Browsers send cookies and Origin on WebSocket upgrades but CORS doesn't apply, so check both here.
    if ws.headers.get("origin") not in settings.allowed_origins:
        await ws.close(code=4403, reason="Origin not allowed")
        return
    db = next(get_db())
    try:
        principal = principal_from_cookie(ws.cookies.get(COOKIE), db)
    except AppError as e:
        await ws.close(code=4401, reason=e.message)
        return
    finally:
        db.close()
    mgr = registry.terminal()
    try:
        session = mgr.get(sid, principal.user.id)
    except TerminalError:
        await ws.close(code=4404, reason="Terminal session not found")
        return
    if session.status != "ready":
        await ws.close(code=4409, reason=session.error or "Terminal is not ready")
        return

    await ws.accept()
    try:
        shell = await asyncio.to_thread(mgr.backend.exec_shell, session.pod, asyncio.get_running_loop())
    except Exception as e:
        log.warning("exec into %s failed: %s", session.pod, e)
        await ws.send_text(json.dumps({"type": "status", "state": "closed", "reason": f"Couldn't attach: {e}"}))
        await ws.close(code=1011)
        return

    session.attached += 1
    mgr.touch(session)
    await ws.send_text(json.dumps({"type": "status", "state": "connected"}))

    async def pump_out() -> str:
        async for chunk in shell.output():
            await ws.send_bytes(chunk)
        return "The shell exited. Open it again to start a new shell in the same sandbox."

    async def pump_in() -> str:
        while True:
            msg = await ws.receive_text()
            try:
                m = json.loads(msg)
            except ValueError:
                continue
            if m.get("type") == "input" and isinstance(m.get("data"), str):
                mgr.touch(session)
                await asyncio.to_thread(shell.write, m["data"].encode()[:65536])
            elif m.get("type") == "resize":
                cols, rows = m.get("cols"), m.get("rows")
                if isinstance(cols, int) and isinstance(rows, int) and 0 < cols <= 1000 and 0 < rows <= 500:
                    await asyncio.to_thread(shell.resize, cols, rows)

    async def watch_session() -> str:
        while session.status == "ready":
            await asyncio.sleep(1)
        return session.error or "Terminal closed"

    tasks = [asyncio.create_task(t()) for t in (pump_out, pump_in, watch_session)]
    reason = "Disconnected"
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        task = done.pop()
        exc = task.exception()
        if exc is None:
            reason = task.result()
        elif not isinstance(exc, WebSocketDisconnect):
            log.info("terminal %s stream error: %s", sid, exc)
    finally:
        for t in tasks:
            t.cancel()
        session.attached -= 1
        await asyncio.to_thread(shell.close)
        with contextlib.suppress(Exception):
            await ws.send_text(json.dumps({"type": "status", "state": "closed", "reason": reason}))
            await ws.close()
