from fastapi import APIRouter, Depends, Query

from ...auth.deps import current_principal
from ...core.errors import AppError
from ...providers import registry
from ...providers.cluster import ClusterUnavailable

router = APIRouter(prefix="/cluster", tags=["cluster"], dependencies=[Depends(current_principal)])


@router.get("/summary")
def summary():
    return registry.cluster().summary()


@router.get("/pods")
def pods(namespace: str | None = Query(None, pattern=r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")):
    try:
        return registry.cluster().pods(namespace)
    except ClusterUnavailable as e:
        raise AppError(503, "cluster_unreachable", str(e)) from e
