"""Lab provisioning (engine used from Phase 4).

NamespaceLabProvisioner resets a lab by deleting only the namespaces that its
known-good manifests mark with devopslab.io/resettable=true, then re-applying
them. See docs/security/lab-isolation.md.
"""
import re
import subprocess
from pathlib import Path
from typing import Protocol

import yaml

from ..core.config import settings

LAB_DIR_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
RESETTABLE = "devopslab.io/resettable"
PROTECTED = {"default", "kube-system", "kube-public", "kube-node-lease", "ingress-nginx"}


class LabError(Exception):
    def __init__(self, message: str, step: str = "unknown"):
        super().__init__(message)
        self.step = step


class LabProvisioner(Protocol):
    def deploy(self, source: str) -> list[str]: ...
    def reset(self, source: str) -> dict: ...


class NamespaceLabProvisioner:
    def __init__(self, labs_root: Path):
        self.labs_root = labs_root

    def _kubectl(self, *args: str, step: str) -> str:
        cmd = ["kubectl", "--kubeconfig", str(settings.kubeconfig), "--context", settings.kube_context, *args]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise LabError(str(e), step) from e
        if res.returncode != 0:
            raise LabError(res.stderr.strip() or f"kubectl {args[0]} failed", step)
        return res.stdout

    def source_dir(self, source: str) -> Path:
        if not LAB_DIR_ID.match(source):
            raise LabError("invalid lab source id", "validate")
        d = (self.labs_root / source).resolve()
        if d.parent != self.labs_root.resolve() or not (d / "kustomization.yaml").exists():
            raise LabError(f"lab source '{source}' has no kustomization.yaml", "validate")
        return d

    def namespaces(self, source: str) -> list[str]:
        rendered = self._kubectl("kustomize", str(self.source_dir(source)), step="render")
        names = []
        for doc in yaml.safe_load_all(rendered):
            if doc and doc.get("kind") == "Namespace":
                meta = doc.get("metadata", {})
                if (meta.get("labels") or {}).get(RESETTABLE) == "true" and meta["name"] not in PROTECTED \
                        and not meta["name"].startswith("devopslab-"):
                    names.append(meta["name"])
        if not names:
            raise LabError("lab declares no resettable namespace; refusing to reset", "render")
        return names

    def deploy(self, source: str) -> list[str]:
        return self._kubectl("apply", "-k", str(self.source_dir(source)), step="apply").strip().splitlines()

    def reset(self, source: str) -> dict:
        namespaces = self.namespaces(source)
        for ns in namespaces:
            self._kubectl("delete", "namespace", ns, "--ignore-not-found", "--wait=true", "--timeout=180s",
                          step=f"delete namespace {ns}")
        return {"reset_namespaces": namespaces, "applied": self.deploy(source)}
