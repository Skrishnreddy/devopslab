from fastapi import APIRouter, HTTPException

from ..services import k8s

router = APIRouter(prefix="/api/cluster", tags=["cluster"])


@router.get("/summary")
def cluster_summary():
    return k8s.summary()


@router.get("/pods")
def cluster_pods(namespace: str | None = None):
    try:
        return k8s.pods(namespace)
    except k8s.ClusterUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(503, f"cluster unreachable: {e.__class__.__name__}") from e
