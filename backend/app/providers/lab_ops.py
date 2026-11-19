"""Start/stop the lab VM and cluster from the UI with the same scripts as `make up` / `make down`.

One operation at a time. Output is kept in memory (last 300 lines) so the UI
can show progress and the real error if a step fails.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field

from ..core.config import REPO_ROOT

log = logging.getLogger("devopslab.lab")
SCRIPTS = {
    "start": [str(REPO_ROOT / "infra" / "scripts" / "up.sh")],
    "stop": [str(REPO_ROOT / "infra" / "scripts" / "down.sh")],
}
TIMEOUT = 20 * 60


@dataclass
class Operation:
    action: str
    state: str = "running"  # running | succeeded | failed
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    exit_code: int | None = None
    lines: deque[str] = field(default_factory=lambda: deque(maxlen=300))

    def view(self) -> dict:
        return {"action": self.action, "state": self.state, "started_at": self.started_at,
                "finished_at": self.finished_at, "exit_code": self.exit_code, "output": list(self.lines)}


class LabOperations:
    def __init__(self, scripts: dict[str, list[str]] | None = None):
        self.scripts = scripts or SCRIPTS
        self.current: Operation | None = None
        self._task: asyncio.Task | None = None

    def start(self, action: str) -> Operation:
        if action not in self.scripts:
            raise ValueError(action)
        if self.current and self.current.state == "running":
            raise RuntimeError(f"'{self.current.action}' is still running")
        op = Operation(action)
        self.current = op
        self._task = asyncio.create_task(self._run(op))
        return op

    async def _run(self, op: Operation) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                *self.scripts[op.action], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            if proc.stdout is None:  # pragma: no cover
                raise RuntimeError("no output pipe")
            async with asyncio.timeout(TIMEOUT):
                async for raw in proc.stdout:
                    op.lines.append(_strip_ansi(raw.decode(errors="replace").rstrip()))
                op.exit_code = await proc.wait()
            op.state = "succeeded" if op.exit_code == 0 else "failed"
        except TimeoutError:
            proc.kill()
            op.lines.append(f"Stopped after {TIMEOUT // 60} minutes.")
            op.state = "failed"
        except Exception as e:
            op.lines.append(f"{e.__class__.__name__}: {e}")
            op.state = "failed"
        finally:
            op.finished_at = time.time()
            log.info("lab %s %s (exit %s)", op.action, op.state, op.exit_code)


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", s)
