"""Terminal sessions in disposable sandbox pods (docs/security/terminal.md).

Each session is one pod in `devopslab-terminal`. A browser WebSocket is bridged
to the Kubernetes exec API of that pod; nothing ever runs on the host.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol

from kubernetes import client
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
from kubernetes.stream.ws_client import ERROR_CHANNEL, RESIZE_CHANNEL

from ..core.config import settings
from .cluster import ClusterUnavailable

log = logging.getLogger("devopslab.terminal")

Profile = Literal["linux", "kubernetes", "docker"]
NAMESPACE = "devopslab-terminal"
IMAGE = "devopslab/terminal:0.1.0"
COMPONENT_LABEL = "devopslab.io/component"
SESSION_LABEL = "devopslab.io/terminal-session"
PROFILE_LABEL = "devopslab.io/terminal-profile"
OWNER_LABEL = "devopslab.io/owner"
SUPPORTED: tuple[Profile, ...] = ("linux", "kubernetes")


class TerminalError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def new_session_id() -> str:
    return "t-" + secrets.token_hex(16)  # 128-bit random, valid DNS label


def pod_name(session_id: str) -> str:
    return f"term-{session_id[2:]}"


def build_pod(session_id: str, user_id: int, profile: Profile) -> dict:
    """The sandbox pod. Every field here is asserted by tests against the spec."""
    if profile not in SUPPORTED:
        raise TerminalError("unsupported_profile", f"The {profile} terminal is not available yet", 400)
    kube = profile == "kubernetes"
    volumes = [
        {"name": "home", "emptyDir": {"sizeLimit": "256Mi"}},
        {"name": "tmp", "emptyDir": {"sizeLimit": "64Mi"}},
    ]
    mounts = [{"name": "home", "mountPath": "/home/learner"}, {"name": "tmp", "mountPath": "/tmp"}]  # noqa: S108 - pod path
    env = [
        {"name": "DEVOPSLAB_PROFILE", "value": profile},
        {"name": "DEVOPSLAB_MAX_SECONDS", "value": str(settings.terminal_max_seconds)},
    ]
    if kube:
        volumes.append({"name": "kubeconfig", "configMap": {"name": "terminal-kubeconfig"}})
        mounts.append({"name": "kubeconfig", "mountPath": "/etc/devopslab/kube", "readOnly": True})
        env.append({"name": "KUBECONFIG", "value": "/etc/devopslab/kube/config"})
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name(session_id),
            "namespace": NAMESPACE,
            "labels": {
                COMPONENT_LABEL: "terminal",
                SESSION_LABEL: session_id,
                PROFILE_LABEL: profile,
                OWNER_LABEL: str(user_id),
                "devopslab.io/managed": "true",
            },
        },
        "spec": {
            "restartPolicy": "Never",
            "activeDeadlineSeconds": settings.terminal_max_seconds,
            "terminationGracePeriodSeconds": 1,
            "enableServiceLinks": False,
            "automountServiceAccountToken": kube,
            "serviceAccountName": "lab-learner" if kube else "default",
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 1000,
                "runAsGroup": 1000,
                "fsGroup": 1000,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [{
                "name": "shell",
                "image": IMAGE,
                "imagePullPolicy": "IfNotPresent",
                "env": env,
                "volumeMounts": mounts,
                "securityContext": {
                    "allowPrivilegeEscalation": False,
                    "readOnlyRootFilesystem": True,
                    "privileged": False,
                    "capabilities": {"drop": ["ALL"]},
                },
                "resources": {
                    "requests": {"cpu": "50m", "memory": "64Mi", "ephemeral-storage": "64Mi"},
                    "limits": {"cpu": "500m", "memory": "512Mi", "ephemeral-storage": "1Gi"},
                },
            }],
            "volumes": volumes,
        },
    }


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
@dataclass
class Session:
    id: str
    user_id: int
    profile: Profile
    pod: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    status: str = "starting"  # starting | ready | closed | failed
    error: str | None = None
    attached: int = 0

    def view(self) -> dict:
        return {"id": self.id, "profile": self.profile, "status": self.status, "error": self.error,
                "created_at": self.created_at, "last_activity": self.last_activity,
                "idle_timeout_seconds": settings.terminal_idle_seconds,
                "max_seconds": settings.terminal_max_seconds}


class Stream(Protocol):
    def write(self, data: bytes) -> None: ...
    def resize(self, cols: int, rows: int) -> None: ...
    def output(self) -> AsyncIterator[bytes]: ...
    def close(self) -> None: ...


class PodBackend(Protocol):
    """The Kubernetes operations the manager needs; faked in tests."""

    def create(self, manifest: dict) -> None: ...
    def wait_ready(self, name: str, timeout: float) -> None: ...
    def delete(self, name: str) -> None: ...
    def list_sessions(self) -> list[str]: ...
    def exec_shell(self, name: str, loop: asyncio.AbstractEventLoop) -> Stream: ...


# --------------------------------------------------------------------------
# Kubernetes implementation
# --------------------------------------------------------------------------
class ExecStream:
    """Bridges a kubernetes WSClient (blocking) to asyncio."""

    def __init__(self, ws, loop: asyncio.AbstractEventLoop):
        self._ws = ws
        self._loop = loop
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._closed = False
        self._lock = threading.Lock()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        try:
            while self._ws.is_open() and not self._closed:
                self._ws.update(timeout=1)
                for channel in (1, 2):
                    data = self._ws.read_channel(channel) if self._ws.peek_channel(channel) else ""
                    if data:
                        chunk = data.encode() if isinstance(data, str) else data
                        self._loop.call_soon_threadsafe(self._queue.put_nowait, chunk)
                if self._ws.peek_channel(ERROR_CHANNEL):
                    self._ws.read_channel(ERROR_CHANNEL)  # exit status of the shell
                    break
        except Exception as e:  # pragma: no cover - network errors
            log.info("exec stream ended: %s", e)
        finally:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, None)

    def write(self, data: bytes) -> None:
        with self._lock:
            if not self._closed:
                self._ws.write_stdin(data.decode(errors="replace"))

    def resize(self, cols: int, rows: int) -> None:
        with self._lock:
            if not self._closed:
                self._ws.write_channel(RESIZE_CHANNEL, json.dumps({"Width": cols, "Height": rows}))

    async def output(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                return
            yield chunk

    def close(self) -> None:
        with self._lock:
            self._closed = True
            with contextlib.suppress(Exception):
                self._ws.close()


class KubePodBackend:
    def __init__(self, api_factory):
        self._api_factory = api_factory

    def _core(self) -> client.CoreV1Api:
        return client.CoreV1Api(self._api_factory())

    def create(self, manifest: dict) -> None:
        try:
            self._core().create_namespaced_pod(NAMESPACE, manifest, _request_timeout=10)
        except ApiException as e:
            reason = json.loads(e.body).get("message", e.reason) if e.body else e.reason
            raise TerminalError("pod_create_failed", f"Couldn't create the sandbox pod: {reason}") from e

    def wait_ready(self, name: str, timeout: float) -> None:
        core = self._core()
        deadline = time.time() + timeout
        last = "Pending"
        while time.time() < deadline:
            pod = core.read_namespaced_pod(name, NAMESPACE, _request_timeout=5)
            phase = pod.status.phase
            statuses = pod.status.container_statuses or []
            waiting = next((s.state.waiting for s in statuses if s.state and s.state.waiting), None)
            if waiting and waiting.reason in {"ErrImagePull", "ImagePullBackOff", "ErrImageNeverPull",
                                              "CreateContainerConfigError", "CreateContainerError"}:
                hint = " Run `make images` to build and load it." if "Image" in waiting.reason else ""
                raise TerminalError("pod_failed", f"Sandbox pod failed: {waiting.reason}: "
                                                  f"{waiting.message or ''}{hint}".strip())
            if phase == "Running" and statuses and all(s.ready for s in statuses):
                return
            if phase in {"Failed", "Succeeded"}:
                raise TerminalError("pod_failed", f"Sandbox pod ended unexpectedly ({phase})")
            last = waiting.reason if waiting else phase
            time.sleep(0.5)
        raise TerminalError("pod_timeout", f"Sandbox pod wasn't ready after {int(timeout)}s (last state: {last})")

    def delete(self, name: str) -> None:
        try:
            self._core().delete_namespaced_pod(name, NAMESPACE, grace_period_seconds=0, _request_timeout=10)
        except ApiException as e:
            if e.status != 404:
                raise

    def list_sessions(self) -> list[str]:
        pods = self._core().list_namespaced_pod(
            NAMESPACE, label_selector=f"{COMPONENT_LABEL}=terminal", _request_timeout=10).items
        return [p.metadata.labels.get(SESSION_LABEL, "") for p in pods]

    def exec_shell(self, name: str, loop: asyncio.AbstractEventLoop) -> Stream:
        # Runs in a worker thread; `loop` is the event loop that consumes the output.
        ws = stream(
            self._core().connect_get_namespaced_pod_exec, name, NAMESPACE, container="shell",
            command=["/bin/bash", "-l"], stdin=True, stdout=True, stderr=True, tty=True,
            _preload_content=False,
        )
        return ExecStream(ws, loop)


# --------------------------------------------------------------------------
# Manager: session lifecycle, limits, timeouts, orphan cleanup
# --------------------------------------------------------------------------
class TerminalManager:
    def __init__(self, backend: PodBackend, clock=time.time):
        self.backend = backend
        self.clock = clock
        self.sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self.on_close = None  # optional callback(session_id, reason), e.g. the audit log

    def for_user(self, user_id: int) -> list[Session]:
        return [s for s in self.sessions.values() if s.user_id == user_id and s.status != "closed"]

    def get(self, session_id: str, user_id: int) -> Session:
        s = self.sessions.get(session_id)
        if s is None or s.user_id != user_id or s.status == "closed":
            raise TerminalError("not_found", "Terminal session not found", 404)
        return s

    async def open(self, user_id: int, profile: Profile) -> Session:
        if profile not in SUPPORTED:
            raise TerminalError("unsupported_profile", f"The {profile} terminal is not available yet", 400)
        async with self._lock:
            if len(self.for_user(user_id)) >= settings.terminal_max_sessions:
                raise TerminalError("too_many_sessions",
                                    f"You can have {settings.terminal_max_sessions} terminals open. Close one first.")
            sid = new_session_id()
            s = Session(id=sid, user_id=user_id, profile=profile, pod=pod_name(sid),
                        created_at=self.clock(), last_activity=self.clock())
            self.sessions[sid] = s
        try:
            await asyncio.to_thread(self.backend.create, build_pod(sid, user_id, profile))
            await asyncio.to_thread(self.backend.wait_ready, s.pod, settings.terminal_start_timeout_seconds)
            s.status = "ready"
        except Exception as e:
            # Never leave a half-started pod behind, and report the real reason.
            self.sessions.pop(sid, None)
            await self._delete_pod(s)
            if isinstance(e, TerminalError):
                raise
            if isinstance(e, ClusterUnavailable):
                raise TerminalError("cluster_unreachable", f"The lab cluster isn't reachable: {e}", 503) from e
            raise TerminalError("pod_create_failed", f"Couldn't start the terminal: {e.__class__.__name__}: {e}") from e
        log.info("terminal %s opened (%s) for user %s", sid, profile, user_id)
        return s

    async def close(self, s: Session, reason: str) -> None:
        if s.status == "closed":
            return
        s.status, s.error = "closed", reason
        await self._delete_pod(s)
        log.info("terminal %s closed: %s", s.id, reason)
        if self.on_close:
            try:
                await asyncio.to_thread(self.on_close, s.id, reason)
            except Exception as e:
                log.warning("couldn't record close of %s: %s", s.id, e)

    async def _delete_pod(self, s: Session) -> None:
        try:
            await asyncio.to_thread(self.backend.delete, s.pod)
        except Exception as e:
            log.warning("couldn't delete pod %s: %s", s.pod, e)

    def touch(self, s: Session) -> None:
        s.last_activity = self.clock()

    async def reap(self) -> list[str]:
        """Close idle and over-age sessions. Returns the closed ids."""
        now = self.clock()
        closed = []
        for s in list(self.sessions.values()):
            if s.status != "ready":
                continue
            if now - s.created_at >= settings.terminal_max_seconds:
                await self.close(s, "Session reached its maximum length")
                closed.append(s.id)
            elif now - s.last_activity >= settings.terminal_idle_seconds:
                await self.close(s, "Closed after being idle")
                closed.append(s.id)
        for sid in [k for k, v in self.sessions.items() if v.status in {"closed", "failed"}
                    and now - v.last_activity > 3600]:
            self.sessions.pop(sid, None)
        return closed

    async def reap_orphans(self) -> int:
        """Delete terminal pods this process doesn't know about (e.g. after a restart)."""
        known = {s.id for s in self.sessions.values() if s.status in {"starting", "ready"}}
        orphans = [sid for sid in await asyncio.to_thread(self.backend.list_sessions) if sid and sid not in known]
        for sid in orphans:
            await asyncio.to_thread(self.backend.delete, pod_name(sid))
        if orphans:
            log.info("deleted %d orphaned terminal pod(s)", len(orphans))
        return len(orphans)

    async def close_all(self) -> None:
        for s in list(self.sessions.values()):
            await self.close(s, "Server shutting down")
