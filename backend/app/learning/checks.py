"""Run lesson checks against the learner's namespace. Read-only; every result says what was observed.

Checks never reveal the expected answer of an `answer` check, and never touch other namespaces.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ..content.models import Check
from ..providers.cluster import ClusterAPIError

NAMESPACE = "lab-playground"
_CORE = "/api/v1/namespaces/{ns}/"
_APPS = "/apis/apps/v1/namespaces/{ns}/"
PATHS = {"Pod": _CORE + "pods", "Service": _CORE + "services", "Endpoints": _CORE + "endpoints",
         "ConfigMap": _CORE + "configmaps", "Deployment": _APPS + "deployments", "ReplicaSet": _APPS + "replicasets"}
MISSING = object()
_SEGMENT = re.compile(r"^([^\[\]]+)((?:\[\d+\])*)$")

Getter = Callable[[str, dict[str, str] | None], dict]


def resolve(obj: Any, path: str) -> Any:
    """`spec.containers[0].image` → value, or MISSING."""
    cur = obj
    for part in path.split("."):
        m = _SEGMENT.match(part)
        if not m:
            return MISSING
        cur = cur.get(m.group(1), MISSING) if isinstance(cur, dict) else MISSING
        for idx in re.findall(r"\[(\d+)\]", m.group(2)):
            cur = cur[int(idx)] if isinstance(cur, list) and int(idx) < len(cur) else MISSING
        if cur is MISSING:
            return MISSING
    return cur


def _same(observed: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(observed, bool):
        return str(observed).lower() == str(expected).lower()
    return str(observed) == str(expected)


def pod_state(pod: dict) -> tuple[bool, str]:
    """(ready, short status like kubectl's STATUS column)."""
    status = pod.get("status", {})
    if pod.get("metadata", {}).get("deletionTimestamp"):
        return False, "Terminating"
    containers = status.get("containerStatuses") or []
    for c in containers:
        waiting = (c.get("state") or {}).get("waiting")
        if waiting:
            return False, waiting.get("reason") or "Waiting"
        terminated = (c.get("state") or {}).get("terminated")
        if terminated:
            return False, terminated.get("reason") or "Terminated"
    phase = status.get("phase", "Unknown")
    ready = phase == "Running" and bool(containers) and all(c.get("ready") for c in containers)
    return ready, phase if ready or phase != "Running" else "Running, not ready"


class CheckRunner:
    def __init__(self, get: Getter, namespace: str = NAMESPACE):
        self.get, self.ns = get, namespace

    def _path(self, kind: str, name: str | None = None) -> str:
        base = PATHS[kind].format(ns=self.ns)
        return f"{base}/{name}" if name else base

    def _obj(self, kind: str, name: str) -> dict | None:
        try:
            return self.get(self._path(kind, name), None)
        except ClusterAPIError as e:
            if e.status == 404:
                return None
            raise

    def run(self, check: Check) -> dict:
        try:
            passed, observed = getattr(self, f"_{check.type}")(check)
        except ClusterAPIError as e:
            passed, observed = False, f"Kubernetes API error: {e.message}"
        return {"description": check.description, "passed": passed, "observed": observed}

    def run_all(self, checks: list[Check]) -> list[dict]:
        return [self.run(c) for c in checks]

    # ---- check types -----------------------------------------------------------
    def _exists(self, c: Check):
        obj = self._obj(c.kind, c.name)
        return obj is not None, f"{c.kind} {c.name} {'exists' if obj else 'not found'} in {self.ns}"

    def _absent(self, c: Check):
        obj = self._obj(c.kind, c.name)
        return obj is None, f"{c.kind} {c.name} {'still exists' if obj else 'not found'} in {self.ns}"

    def _field(self, c: Check):
        obj = self._obj(c.kind, c.name)
        if obj is None:
            return False, f"{c.kind} {c.name} not found in {self.ns}"
        value = resolve(obj, c.path)
        if value is MISSING:
            return False, f"{c.path} is not set"
        return _same(value, c.equals), f"{c.path} = {value}"

    def _pods_ready(self, c: Check):
        selector = ",".join(f"{k}={v}" for k, v in c.selector.items())
        pods = self.get(self._path("Pod"), {"labelSelector": selector}).get("items", [])
        states = [(p["metadata"]["name"], *pod_state(p)) for p in pods]
        ready = sum(1 for _, r, _ in states if r)
        need = c.min if c.min is not None else 1
        passed = ready >= need and (not c.all_ready or ready == len(states))
        detail = ", ".join(f"{n} ({s})" for n, _, s in states) or "none"
        return passed, f"{ready} of {len(states)} pods with {selector} ready: {detail}"

    def _rollout_ready(self, c: Check):
        d = self._obj("Deployment", c.name)
        if d is None:
            return False, f"Deployment {c.name} not found in {self.ns}"
        want = d.get("spec", {}).get("replicas", 1)
        st = d.get("status", {})
        ready, updated = st.get("readyReplicas", 0), st.get("updatedReplicas", 0)
        current = st.get("observedGeneration", 0) >= d.get("metadata", {}).get("generation", 0)
        passed = current and ready == want and updated == want and st.get("replicas", 0) == want \
            and (c.min is None or ready >= c.min)
        return passed, f"ready {ready}/{want}, up to date {updated}/{want}"

    def _endpoints(self, c: Check):
        ep = self._obj("Endpoints", c.name)
        if ep is None:
            return False, f"Endpoints {c.name} not found (is there a Service called {c.name}?)"
        subsets = ep.get("subsets") or []
        ready = sum(len(s.get("addresses") or []) for s in subsets)
        not_ready = sum(len(s.get("notReadyAddresses") or []) for s in subsets)
        need = c.min if c.min is not None else 1
        return ready >= need, f"{ready} ready endpoint address(es), {not_ready} not ready"

    def _answer(self, c: Check):
        cm = self._obj("ConfigMap", c.name)
        if cm is None:
            return False, f"ConfigMap {c.name} not found in {self.ns}"
        given = (cm.get("data") or {}).get(c.key)
        if given is None:
            return False, f"ConfigMap {c.name} has no key {c.key}"
        return given.strip() == self._truth(c.source), f"you answered {c.key}={given.strip()!r}"

    def _truth(self, source: str) -> str:
        if source == "server_minor_version":
            return str(self.get("/version", None).get("minor", "")).rstrip("+")
        nodes = self.get("/api/v1/nodes", None).get("items", [])
        if source == "node_count":
            return str(len(nodes))
        names = [n["metadata"]["name"] for n in nodes
                 if "node-role.kubernetes.io/control-plane" in (n["metadata"].get("labels") or {})]
        return names[0] if names else ""
