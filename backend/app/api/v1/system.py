"""Health, features, infrastructure checks and settings."""
import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from ... import __version__
from ...auth.deps import current_principal
from ...core.config import settings
from ...providers import registry
from ...providers.health import worst

public = APIRouter(tags=["system"])
router = APIRouter(tags=["system"], dependencies=[Depends(current_principal)])

# Single source of truth for what the UI may present as working.
FEATURES = [
    ("dashboard", "Dashboard", "available", 1),
    ("infra-health", "Infrastructure health", "available", 1),
    ("kubernetes-pods", "Pods and nodes", "available", 1),
    ("learn-catalog", "Learning catalog and progress", "available", 1),
    ("terminal", "Integrated terminal", "planned", 2),
    ("kubernetes-explorer", "Deployments, services, logs, events", "planned", 3),
    ("labs", "Lab management (deploy, reset)", "planned", 4),
    ("cloudmart", "CloudMart project", "planned", 4),
    ("lessons", "Lessons, exercises and checks", "planned", 5),
    ("troubleshooting", "Troubleshooting challenges", "planned", 6),
    ("monitoring", "Prometheus, Grafana, Loki", "planned", 7),
    ("devsecops", "Trivy, Kyverno, policies", "planned", 8),
    ("ai-teacher", "Local AI Teacher (Ollama)", "planned", 9),
    ("cicd", "Jenkins, Argo CD", "planned", 10),
]


@public.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@router.get("/features")
def features():
    return [{"id": i, "name": n, "status": s, "phase": p} for i, n, s, p in FEATURES]


@router.get("/infra/health")
async def infra_health():
    runtime, cluster, ai = await asyncio.gather(
        registry.runtime().health(), registry.cluster().health(), registry.ai().health()
    )
    components = [*runtime, *cluster, ai]
    return {
        "overall": worst([c.status for c in components if not c.optional]),
        "checked_at": datetime.now(UTC),
        "components": [c.model_dump() for c in components],
    }


@router.get("/settings")
def get_settings():
    return {
        "environment": {
            "data_dir": str(settings.data_dir),
            "database": settings.resolved_database_url.split("://", 1)[0],
            "kubeconfig": str(settings.kubeconfig),
            "kube_context": settings.kube_context,
            "cluster_name": settings.cluster_name,
            "colima_profile": settings.colima_profile,
            "docker_context": settings.docker_context,
        },
        "session_hours": settings.session_hours,
        "ai": {"enabled": settings.ai_enabled, "provider": "ollama", "base_url": settings.ollama_url,
               "local": True, "status": "planned", "phase": 9},
    }
