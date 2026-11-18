"""Integrated terminal (Stage 3).

Design (see docs/architecture.md): every terminal is a WebSocket bridged to a
`kubectl exec`-style stream into a sandbox pod in the devopslab-terminal
namespace. The backend never spawns a shell on the Mac itself.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/terminal", tags=["terminal"])

PROFILES = [
    {"id": "linux", "name": "Linux", "image": "devopslab/term-linux",
     "description": "Ubuntu sandbox with systemd for systemctl and journalctl practice"},
    {"id": "kubernetes", "name": "Kubernetes", "image": "devopslab/term-kube",
     "description": "kubectl, helm and k9s, bound to a lab ServiceAccount"},
    {"id": "docker", "name": "Docker / DevOps", "image": "devopslab/term-docker",
     "description": "Docker CLI talking to a rootless docker-in-docker sidecar, not your Mac"},
]


@router.get("/profiles")
def profiles():
    return {"available": False, "stage": 3, "profiles": PROFILES}
