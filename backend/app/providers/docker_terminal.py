"""Docker terminal sandboxes (Phase 2b) in the separate Docker VM.

The Docker VM (Colima profile `devopslab-docker`) is the isolation boundary:
nothing from the Mac is mounted into it and a firewall keeps its containers
away from the Mac's localhost (infra/docker-vm/setup.sh). Each session is
one container running its own rootless Docker engine, on its own network.
The backend talks to the VM's Docker API over Colima's local unix socket; no
shell or PTY is ever started on the host.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import subprocess
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, NotFound

from ..core.config import REPO_ROOT, settings
from .terminal import (
    COMPONENT_LABEL,
    OWNER_LABEL,
    PROFILE_LABEL,
    SESSION_LABEL,
    Profile,
    TerminalError,
    pod_name,
)

log = logging.getLogger("devopslab.terminal.docker")
DOCKER_IMAGE = "devopslab/docker-terminal:0.1.0"  # built by infra/scripts/docker-vm.sh
SCRIPT = REPO_ROOT / "infra" / "scripts" / "docker-vm.sh"
# `docker version` (unlike `docker info --format`) exits non-zero when the daemon is unreachable.
READY_CHECK = ('docker version --format "{{.Server.Version}}" >/dev/null 2>&1 && echo READY '
               '|| { pgrep -f "dockerd|rootlesskit" >/dev/null && echo STARTING || echo DEAD; }')


def network_name(session_id: str) -> str:
    return f"dl-{session_id[2:]}"


def build_container(session_id: str, user_id: int) -> dict:
    """Container spec for one Docker sandbox. Asserted field by field in tests."""
    labels = {
        COMPONENT_LABEL: "terminal",
        SESSION_LABEL: session_id,
        PROFILE_LABEL: "docker",
        OWNER_LABEL: str(user_id),
        "devopslab.io/managed": "true",
    }
    return {
        "image": DOCKER_IMAGE,
        "name": pod_name(session_id),
        "hostname": "devopslab",
        "labels": labels,
        "environment": {"DEVOPSLAB_PROFILE": "docker", "DEVOPSLAB_MAX_SECONDS": str(settings.terminal_max_seconds)},
        "network": network_name(session_id),
        "host_config": {
            # Required by rootless docker-in-docker (nested user namespaces). The
            # learner and their daemon still run as uid 1000; the VM is the boundary.
            "privileged": True,
            # Allows user namespaces for this container only (infra/docker-vm/setup.sh).
            "security_opt": ["apparmor=devopslab-sandbox"],
            "binds": [],  # no host paths, no Docker socket
            "mem_limit": "1g",
            "memswap_limit": "1g",
            "nano_cpus": 1_000_000_000,
            "pids_limit": 1024,
            "network_mode": network_name(session_id),
            "log_config": {"type": "json-file", "config": {"max-size": "1m", "max-file": "1"}},
            "init": False,  # the image runs tini
        },
    }


class DockerExecStream:
    """Raw TTY stream of a `docker exec`, bridged to asyncio."""

    def __init__(self, api, exec_id: str, sock, loop: asyncio.AbstractEventLoop):
        self._api, self._exec_id, self._loop = api, exec_id, loop
        self._sock = getattr(sock, "_sock", sock)
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._closed = False
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        try:
            while not self._closed:
                data = self._sock.recv(4096)
                if not data:
                    break
                self._loop.call_soon_threadsafe(self._queue.put_nowait, data)
        except OSError as e:
            log.info("docker exec stream ended: %s", e)
        finally:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, None)

    def write(self, data: bytes) -> None:
        if not self._closed:
            self._sock.sendall(data)

    def resize(self, cols: int, rows: int) -> None:
        if not self._closed:
            with contextlib.suppress(APIError):
                self._api.exec_resize(self._exec_id, height=rows, width=cols)

    async def output(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                return
            yield chunk

    def close(self) -> None:
        self._closed = True
        with contextlib.suppress(OSError):
            self._sock.close()


class DockerVMBackend:
    def __init__(self, clock=time.time, runner=subprocess.run):
        self.clock = clock
        self.runner = runner
        self.idle_since = clock()
        self._vm_lock = threading.Lock()

    @property
    def socket_path(self) -> Path:
        return Path.home() / ".colima" / settings.docker_vm_profile / "docker.sock"

    def _api(self):
        return docker.APIClient(base_url=f"unix://{self.socket_path}", timeout=30, version="auto")

    def vm_running(self) -> bool:
        if not self.socket_path.exists():
            return False
        try:
            return bool(docker.APIClient(base_url=f"unix://{self.socket_path}", timeout=3).ping())
        except (DockerException, OSError):
            return False

    def _script(self, action: str, timeout: float) -> None:
        try:
            r = self.runner([str(SCRIPT), action], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise TerminalError("docker_vm_failed", f"The Docker VM didn't {action} within {int(timeout)}s") from e
        except FileNotFoundError as e:
            raise TerminalError("docker_vm_failed", f"{SCRIPT} not found") from e
        if r.returncode != 0:
            tail = "\n".join((r.stderr or r.stdout or "").strip().splitlines()[-5:])
            raise TerminalError("docker_vm_failed", f"Couldn't {action} the Docker VM: {tail}. "
                                                    f"Try `make docker-vm-{action}` in a terminal.")

    def ensure_vm(self) -> None:
        with self._vm_lock:
            # Always run `up`: it is idempotent and re-applies the firewall after a VM restart.
            self._script("up", settings.docker_vm_start_timeout_seconds)

    # -- PodBackend -----------------------------------------------------------
    def create(self, session_id: str, user_id: int, profile: Profile) -> None:
        if profile != "docker":
            raise TerminalError("unsupported_profile", f"{profile} doesn't run in the Docker VM", 400)
        self.idle_since = self.clock()
        self.ensure_vm()
        spec = build_container(session_id, user_id)
        api = self._api()
        try:
            api.create_network(spec["network"], driver="bridge", labels=spec["labels"])
            hc = api.create_host_config(**spec["host_config"])
            c = api.create_container(spec["image"], name=spec["name"], hostname=spec["hostname"],
                                     labels=spec["labels"], environment=spec["environment"], host_config=hc)
            api.start(c["Id"])
        except DockerException as e:
            raise TerminalError("pod_create_failed", f"Couldn't create the Docker sandbox: {e}") from e

    def _sh(self, api, name: str, script: str) -> str:
        ex = api.exec_create(name, ["sh", "-c", script])
        return api.exec_start(ex["Id"]).decode(errors="replace").strip()

    def wait_ready(self, name: str, timeout: float) -> None:
        """Ready means the learner's own Docker engine answers, not just that the container runs."""
        api = self._api()
        start = time.time()
        while time.time() - start < timeout:
            state = api.inspect_container(name)["State"]
            if not state.get("Running"):
                logs = api.logs(name, tail=5).decode(errors="replace").strip()
                raise TerminalError("pod_failed", f"Docker sandbox stopped ({state.get('Status')}). {logs}".strip())
            out = self._sh(api, name, READY_CHECK)
            if out.endswith("READY"):
                return
            if out.endswith("DEAD") and time.time() - start > 3:
                log_tail = self._sh(api, name, "tail -n 3 /tmp/dockerd.log 2>/dev/null")
                raise TerminalError("pod_failed", f"The sandbox's Docker engine failed to start: {log_tail}")
            time.sleep(1)
        raise TerminalError("pod_timeout", f"The sandbox's Docker engine wasn't ready after {int(timeout)}s")

    def delete(self, name: str) -> None:
        if not self.vm_running():
            return  # stopping the VM already removed nothing persistent we care about
        api = self._api()
        with contextlib.suppress(NotFound):
            api.remove_container(name, force=True, v=True)
        with contextlib.suppress(NotFound):
            api.remove_network(f"dl-{name.removeprefix('term-')}")

    def list_sessions(self) -> list[str]:
        if not self.vm_running():
            return []
        cs = self._api().containers(all=True, filters={"label": f"{COMPONENT_LABEL}=terminal"})
        return [c["Labels"].get(SESSION_LABEL, "") for c in cs]

    def exec_shell(self, name: str, loop: asyncio.AbstractEventLoop) -> DockerExecStream:
        api = self._api()
        ex = api.exec_create(name, ["bash", "-l"], stdin=True, tty=True, workdir="/home/rootless",
                             environment={"TERM": "xterm-256color"})
        sock = api.exec_start(ex["Id"], socket=True, tty=True)
        return DockerExecStream(api, ex["Id"], sock, loop)

    def on_reap(self, active_sessions: int) -> None:
        """Stop the VM once no Docker terminal has used it for docker_vm_idle_seconds."""
        now = self.clock()
        if active_sessions > 0:
            self.idle_since = now
            return
        if now - self.idle_since >= settings.docker_vm_idle_seconds and self.vm_running():
            log.info("Stopping the Docker VM after %ss without Docker terminals", settings.docker_vm_idle_seconds)
            self.idle_since = now
            self._script("down", 120)
