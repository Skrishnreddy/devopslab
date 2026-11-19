"""Lab engine (Phase 4): deploy, stop, start, reset and delete labs from known-good manifests.

A lab is a folder in `labs/<id>/` with a kustomization and a `lab.yaml`. Only
namespaces the manifests label `devopslab.io/resettable=true` are ever deleted,
never `kube-system`, `ingress-nginx` or `devopslab-*`. Every operation is a list
of named steps; a failure stops at that step and reports the real kubectl error.
See docs/security/lab-isolation.md.
"""
from __future__ import annotations

import re
import secrets
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

from ..core.config import settings

LAB_DIR_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
RESETTABLE = "devopslab.io/resettable"
PROTECTED = {"default", "kube-system", "kube-public", "kube-node-lease", "ingress-nginx"}
WAIT_SECONDS = 240
# Pod waiting reasons that never resolve on their own; waiting longer only hides the error.
FATAL_REASONS = ("ErrImageNeverPull", "InvalidImageName", "CreateContainerConfigError")


def kubectl(*args: str, step: str, stdin: str | None = None, timeout: float = 300, runner=None) -> str:
    """Run kubectl against the DevOpsLab cluster. Errors carry kubectl's own message and the step name."""
    cmd = ["kubectl", "--kubeconfig", str(settings.kubeconfig), "--context", settings.kube_context, *args]
    try:
        res = (runner or subprocess.run)(cmd, capture_output=True, text=True, timeout=timeout, check=False,
                                         input=stdin)
    except FileNotFoundError as e:
        raise LabError("kubectl not found. Run `make prereqs`.", step) from e
    except subprocess.TimeoutExpired as e:
        raise LabError(f"kubectl {args[0]} timed out after {int(timeout)}s", step) from e
    if res.returncode != 0:
        raise LabError((res.stderr or res.stdout).strip() or f"kubectl {args[0]} failed", step)
    return res.stdout


class LabError(Exception):
    def __init__(self, message: str, step: str = "unknown"):
        super().__init__(message)
        self.step = step


class LabProvisioner(Protocol):
    def deploy(self, source: str) -> list[str]: ...
    def reset(self, source: str) -> dict: ...


@dataclass
class Step:
    name: str
    state: str = "pending"  # pending | running | ok | failed
    detail: str = ""
    seconds: float | None = None

    def view(self) -> dict:
        return {"name": self.name, "state": self.state, "detail": self.detail, "seconds": self.seconds}


@dataclass
class LabSpec:
    id: str
    url: str | None = None
    generated_secrets: list[dict] = field(default_factory=list)


class NamespaceLabProvisioner:
    def __init__(self, labs_root: Path, runner=subprocess.run):
        self.labs_root = labs_root
        self.runner = runner

    # ---- kubectl ----------------------------------------------------------
    def _kubectl(self, *args: str, step: str, stdin: str | None = None, timeout: float = 300) -> str:
        return kubectl(*args, step=step, stdin=stdin, timeout=timeout, runner=self.runner)

    # ---- sources ------------------------------------------------------------
    def source_dir(self, source: str) -> Path:
        if not LAB_DIR_ID.match(source):
            raise LabError("invalid lab source id", "validate")
        d = (self.labs_root / source).resolve()
        if d.parent != self.labs_root.resolve() or not (d / "kustomization.yaml").exists():
            raise LabError(f"lab source '{source}' has no kustomization.yaml", "validate")
        return d

    def spec(self, source: str) -> LabSpec:
        f = self.source_dir(source) / "lab.yaml"
        data = yaml.safe_load(f.read_text()) if f.exists() else {}
        return LabSpec(id=source, url=data.get("url"), generated_secrets=data.get("generated_secrets", []))

    def render(self, source: str) -> list[dict]:
        rendered = self._kubectl("kustomize", str(self.source_dir(source)), step="render")
        return [d for d in yaml.safe_load_all(rendered) if d]

    def namespaces(self, source: str, docs: list[dict] | None = None) -> list[str]:
        names = []
        for doc in docs if docs is not None else self.render(source):
            if doc.get("kind") == "Namespace":
                meta = doc.get("metadata", {})
                if (meta.get("labels") or {}).get(RESETTABLE) == "true" and meta["name"] not in PROTECTED \
                        and not meta["name"].startswith("devopslab-"):
                    names.append(meta["name"])
        if not names:
            raise LabError("lab declares no resettable namespace; refusing to touch the cluster", "render")
        return names

    # ---- building blocks -----------------------------------------------------
    def create_namespaces(self, docs: list[dict]) -> str:
        ns_docs = [d for d in docs if d.get("kind") == "Namespace"]
        return self._kubectl("apply", "-f", "-", stdin=yaml.safe_dump_all(ns_docs), step="create namespaces")

    def ensure_secrets(self, source: str, namespace: str) -> str:
        """Random credentials, generated in the cluster at deploy time; never written to git or the DB."""
        made = []
        for s in self.spec(source).generated_secrets:
            name = s["name"]
            exists = self._kubectl("get", "secret", name, "-n", namespace, "--ignore-not-found", "-o", "name",
                                   step="generate secrets").strip()
            if exists:
                continue
            manifest = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
                        "metadata": {"name": name, "namespace": namespace,
                                     "labels": {"devopslab.io/generated": "true"}},
                        "stringData": {k: secrets.token_urlsafe(24) for k in s["keys"]}}
            self._kubectl("apply", "-f", "-", stdin=yaml.safe_dump(manifest), step="generate secrets")
            made.append(name)
        return f"created {', '.join(made)}" if made else "already present"

    def apply(self, source: str) -> str:
        return self._kubectl("apply", "-k", str(self.source_dir(source)), step="apply manifests")

    def workloads(self, namespace: str) -> list[str]:
        out = self._kubectl("get", "deployments,statefulsets", "-n", namespace, "-o", "name", step="list workloads")
        return out.split()

    def wait_ready(self, namespaces: list[str]) -> str:
        """Wait for every rollout, checking pods between short waits so errors that never heal fail fast."""
        done = []
        deadline = time.monotonic() + WAIT_SECONDS
        for ns in namespaces:
            for w in self.workloads(ns):
                while True:
                    chunk = max(5, min(15, int(deadline - time.monotonic())))
                    try:
                        self._kubectl("rollout", "status", w, "-n", ns, f"--timeout={chunk}s",
                                      step="wait until ready", timeout=chunk + 15)
                        break
                    except LabError as e:
                        problems = self.pod_problems(ns)
                        fatal = next((r for r in FATAL_REASONS if r in problems), None)
                        if fatal:
                            raise LabError(f"{w} can't start: {fatal} won't fix itself by waiting.\n{problems}",
                                           "wait until ready") from e
                        if "timed out" not in str(e) or time.monotonic() >= deadline:
                            raise LabError(f"{w} isn't ready: {e}\n{problems}", "wait until ready") from e
                done.append(w)
        return f"{len(done)} workloads ready"

    def pod_problems(self, namespace: str) -> str:
        """What a learner would check first: pods that aren't Running/Ready and why."""
        try:
            out = self._kubectl("get", "pods", "-n", namespace, "-o",
                                "custom-columns=POD:.metadata.name,STATUS:.status.phase,"
                                "REASON:.status.containerStatuses[*].state.waiting.reason,"
                                "MESSAGE:.status.containerStatuses[*].state.waiting.message",
                                step="diagnose")
        except LabError as e:
            return f"(couldn't list pods: {e})"
        return out.strip()

    def scale_to_zero(self, namespaces: list[str]) -> str:
        for ns in namespaces:
            if self.workloads(ns):
                self._kubectl("scale", "deployments,statefulsets", "--all", "--replicas=0", "-n", ns,
                              step="scale to zero")
        return "all workloads scaled to 0 (data volumes kept)"

    def delete_namespaces(self, namespaces: list[str]) -> str:
        for ns in namespaces:
            self._kubectl("delete", "namespace", ns, "--ignore-not-found", "--wait=true", "--timeout=180s",
                          step="delete namespaces", timeout=200)
        return f"deleted {', '.join(namespaces)}"

    # ---- operations as step lists --------------------------------------------
    def plan(self, action: str, source: str) -> list[tuple[str, Callable[[dict], str]]]:
        """Named steps for an operation. Each takes and may fill a shared context dict."""

        def render(ctx):
            ctx["docs"] = self.render(source)
            ctx["namespaces"] = self.namespaces(source, ctx["docs"])
            return f"namespaces: {', '.join(ctx['namespaces'])}"

        bring_up = [
            ("create namespaces", lambda ctx: self.create_namespaces(ctx["docs"]).strip()),
            ("generate secrets", lambda ctx: self.ensure_secrets(source, ctx["namespaces"][0])),
            ("apply manifests", lambda ctx: f"{len(self.apply(source).splitlines())} objects applied"),
            ("wait until ready", lambda ctx: self.wait_ready(ctx["namespaces"])),
        ]
        plans = {
            "deploy": [("render manifests", render), *bring_up],
            "start": [("render manifests", render),
                      ("apply manifests", lambda ctx: f"{len(self.apply(source).splitlines())} objects applied"),
                      ("wait until ready", lambda ctx: self.wait_ready(ctx["namespaces"]))],
            "stop": [("render manifests", render),
                     ("scale to zero", lambda ctx: self.scale_to_zero(ctx["namespaces"]))],
            "reset": [("render manifests", render),
                      ("delete namespaces", lambda ctx: self.delete_namespaces(ctx["namespaces"])), *bring_up],
            "delete": [("render manifests", render),
                       ("delete namespaces", lambda ctx: self.delete_namespaces(ctx["namespaces"]))],
        }
        if action not in plans:
            raise LabError(f"unknown action {action}", "validate")
        return plans[action]

    def run(self, action: str, source: str, on_step: Callable[[list[Step]], None] | None = None) -> list[Step]:
        steps_fns = self.plan(action, source)
        steps = [Step(name) for name, _ in steps_fns]
        ctx: dict = {}
        for step, (_, fn) in zip(steps, steps_fns, strict=True):
            step.state = "running"
            if on_step:
                on_step(steps)
            t0 = time.monotonic()
            try:
                step.detail = fn(ctx) or ""
                step.state = "ok"
            except LabError as e:
                step.state, step.detail = "failed", str(e)
                step.seconds = round(time.monotonic() - t0, 1)
                if on_step:
                    on_step(steps)
                raise LabError(str(e), step.name) from e
            step.seconds = round(time.monotonic() - t0, 1)
            if on_step:
                on_step(steps)
        return steps

    # ---- Phase 1 API kept for callers/tests ------------------------------------
    def deploy(self, source: str) -> list[str]:
        return self.apply(source).strip().splitlines()

    def reset(self, source: str) -> dict:
        namespaces = self.namespaces(source)
        self.delete_namespaces(namespaces)
        return {"reset_namespaces": namespaces, "applied": self.deploy(source)}
