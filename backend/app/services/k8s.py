"""Read-only view of the lab cluster for the dashboard.

Everything degrades gracefully: if Colima/kind is not running the API reports
connected=false instead of erroring, so the UI can tell you to run `make up`.
"""
from collections import Counter
from pathlib import Path

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from ..config import settings


class ClusterUnavailable(Exception):
    pass


def _api() -> client.ApiClient:
    if not Path(settings.kubeconfig).exists():
        raise ClusterUnavailable(f"kubeconfig not found at {settings.kubeconfig}; run `make up`")
    try:
        return config.new_client_from_config(
            config_file=settings.kubeconfig, context=settings.kube_context
        )
    except ConfigException as e:
        raise ClusterUnavailable(str(e)) from e


def summary() -> dict:
    try:
        api = _api()
        core, apps = client.CoreV1Api(api), client.AppsV1Api(api)
        nodes = core.list_node(_request_timeout=3).items
        namespaces = core.list_namespace(_request_timeout=3).items
        pods = core.list_pod_for_all_namespaces(_request_timeout=3).items
        deployments = apps.list_deployment_for_all_namespaces(_request_timeout=3).items
    except ClusterUnavailable as e:
        return {"connected": False, "reason": str(e)}
    except Exception as e:  # connection refused, timeouts, auth errors
        return {"connected": False, "reason": f"cluster unreachable: {e.__class__.__name__}"}

    def ready(n) -> bool:
        return any(c.type == "Ready" and c.status == "True" for c in (n.status.conditions or []))

    return {
        "connected": True,
        "context": settings.kube_context,
        "nodes": {
            "total": len(nodes),
            "ready": sum(ready(n) for n in nodes),
            "items": [
                {
                    "name": n.metadata.name,
                    "ready": ready(n),
                    "roles": sorted(
                        k.split("/", 1)[1]
                        for k in (n.metadata.labels or {})
                        if k.startswith("node-role.kubernetes.io/")
                    ) or ["worker"],
                    "version": n.status.node_info.kubelet_version,
                }
                for n in nodes
            ],
        },
        "namespaces": len(namespaces),
        "pods": {"total": len(pods), "by_phase": dict(Counter(p.status.phase for p in pods))},
        "deployments": {
            "total": len(deployments),
            "available": sum(
                (d.status.available_replicas or 0) >= (d.spec.replicas or 0) for d in deployments
            ),
        },
    }


def pods(namespace: str | None = None) -> list[dict]:
    core = client.CoreV1Api(_api())
    items = (
        core.list_namespaced_pod(namespace, _request_timeout=3).items
        if namespace
        else core.list_pod_for_all_namespaces(_request_timeout=3).items
    )
    out = []
    for p in items:
        statuses = p.status.container_statuses or []
        waiting = next((s.state.waiting.reason for s in statuses if s.state and s.state.waiting), None)
        out.append(
            {
                "namespace": p.metadata.namespace,
                "name": p.metadata.name,
                "phase": p.status.phase,
                "status": waiting or p.status.phase,
                "ready": f"{sum(s.ready for s in statuses)}/{len(p.spec.containers)}",
                "restarts": sum(s.restart_count for s in statuses),
                "node": p.spec.node_name,
            }
        )
    return out
