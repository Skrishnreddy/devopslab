"""Lab engine: resettable namespaces for Engineer Mode (used from Stage 4 on).

Each lab lives in labs/<lab_id>/ with a kustomization.yaml whose resources all
target namespaces labelled devopslab.io/resettable=true. Resetting a lab means
deleting those namespaces and re-applying the known-good manifests, so breaking
something never requires rebuilding the cluster.

Safety rules:
  * lab_id must match a directory under labs/ (no path tricks);
  * only namespaces carrying the resettable label are ever deleted;
  * kubectl always runs with the lab's own kubeconfig and context.
"""
import re
import subprocess
from pathlib import Path

import yaml

from ..config import settings

LAB_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
RESETTABLE = "devopslab.io/resettable"


class LabError(Exception):
    pass


def _kubectl(*args: str, input_text: str | None = None) -> str:
    cmd = ["kubectl", "--kubeconfig", settings.kubeconfig, "--context", settings.kube_context, *args]
    res = subprocess.run(cmd, capture_output=True, text=True, input=input_text, timeout=300)
    if res.returncode != 0:
        raise LabError(res.stderr.strip() or f"kubectl {' '.join(args)} failed")
    return res.stdout


def lab_dir(lab_id: str) -> Path:
    if not LAB_ID.match(lab_id):
        raise LabError("invalid lab id")
    d = Path(settings.labs_dir, lab_id).resolve()
    if d.parent != Path(settings.labs_dir).resolve() or not (d / "kustomization.yaml").exists():
        raise LabError(f"lab '{lab_id}' is not installed yet")
    return d


def lab_namespaces(lab_id: str) -> list[str]:
    """Namespaces declared by the lab's manifests that are marked resettable."""
    rendered = _kubectl("kustomize", str(lab_dir(lab_id)))
    names = []
    for doc in yaml.safe_load_all(rendered):
        if doc and doc.get("kind") == "Namespace":
            labels = doc.get("metadata", {}).get("labels", {}) or {}
            if labels.get(RESETTABLE) == "true":
                names.append(doc["metadata"]["name"])
    if not names:
        raise LabError("lab declares no resettable namespace; refusing to reset")
    return names


def deploy(lab_id: str) -> str:
    return _kubectl("apply", "-k", str(lab_dir(lab_id)))


def reset(lab_id: str) -> dict:
    namespaces = lab_namespaces(lab_id)
    for ns in namespaces:
        _kubectl("delete", "namespace", ns, "--ignore-not-found", "--wait=true", "--timeout=180s")
    out = deploy(lab_id)
    return {"lab": lab_id, "reset_namespaces": namespaces, "applied": out.strip().splitlines()}
