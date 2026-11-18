"""Container runtime provider. Phase 1: Colima + Docker Engine on macOS.

A Linux (native Docker/Podman) or Windows (WSL2) runtime implements the same
interface and is selected in config.
"""
import asyncio
import json
import re
from typing import Protocol

from ..core.config import settings
from .commands import run
from .health import ComponentHealth

INSTALL = "Run `make prereqs` (installs with Homebrew)"


class ContainerRuntime(Protocol):
    async def health(self) -> list[ComponentHealth]: ...


def _first_version(text: str) -> str | None:
    m = re.search(r"v?(\d+\.\d+\.\d+)", text)
    return m.group(1) if m else None


class ColimaRuntime:
    async def _colima(self) -> ComponentHealth:
        ver, status = await asyncio.gather(
            run("colima", "version"), run("colima", "status", "-p", settings.colima_profile)
        )
        if ver.missing:
            return ComponentHealth(id="colima", name="Colima", status="missing",
                                   message="Colima is not installed", remediation=INSTALL)
        version = _first_version(ver.stdout)
        if status.ok:
            return ComponentHealth(id="colima", name="Colima", status="ok", version=version,
                                   message=f"Profile '{settings.colima_profile}' is running")
        return ComponentHealth(
            id="colima", name="Colima", status="warning", version=version,
            message=f"Profile '{settings.colima_profile}' is not running",
            remediation="Run `make up`",
            details={"output": (status.stderr or status.stdout)[:300]},
        )

    async def _docker(self) -> ComponentHealth:
        res = await run("docker", "--context", settings.docker_context, "info", "--format", "{{json .}}")
        if res.missing:
            return ComponentHealth(id="docker", name="Docker Engine", status="missing",
                                   message="Docker CLI is not installed", remediation=INSTALL)
        if not res.ok:
            return ComponentHealth(
                id="docker", name="Docker Engine", status="warning",
                message=f"Docker Engine in context '{settings.docker_context}' is not reachable",
                remediation="Start Colima with `make up`",
                details={"output": (res.stderr or "timed out")[:300]},
            )
        try:
            info = json.loads(res.stdout)
        except json.JSONDecodeError:
            return ComponentHealth(id="docker", name="Docker Engine", status="error",
                                   message="Unexpected output from `docker info`")
        return ComponentHealth(
            id="docker", name="Docker Engine", status="ok", version=info.get("ServerVersion"),
            message=f"{info.get('NCPU')} CPU, {round(info.get('MemTotal', 0) / 2**30, 1)} GiB, "
                    f"{info.get('Architecture')}",
            details={"cpus": info.get("NCPU", 0), "memory_bytes": info.get("MemTotal", 0),
                     "containers_running": info.get("ContainersRunning", 0)},
        )

    async def health(self) -> list[ComponentHealth]:
        return list(await asyncio.gather(self._colima(), self._docker()))
