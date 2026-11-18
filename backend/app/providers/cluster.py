"""Kubernetes cluster provider. Phase 1: kind on the local runtime.

All reads go to the real API server. If it is unreachable the caller gets
ClusterUnavailable with the reason; nothing is ever cached or invented.
"""
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from ..core.config import settings
from .commands import run
from .health import ComponentHealth

TIMEOUT = 4


class ClusterUnavailable(Exception):
    pass


class ClusterProvider(Protocol):
    async def health(self) -> list[ComponentHealth]: ...
    def summary(self) -> dict: ...
    def pods(self, namespace: str | None = None) -> list[dict]: ...


def _ready(node) -> bool:
    return any(c.type == "Ready" and c.status == "True" for c in (node.status.conditions or []))


class KindCluster:
    def _api(self) -> client.ApiClient:
        if not Path(settings.kubeconfig).exists():
            raise ClusterUnavailable(f"No kubeconfig at {settings.kubeconfig}. Run `make up`.")
        try:
            return config.new_client_from_config(config_file=str(settings.kubeconfig),
                                                 context=settings.kube_context)
        except ConfigException as e:
            raise ClusterUnavailable(str(e)) from e

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, _request_timeout=TIMEOUT, **kwargs)
        except ClusterUnavailable:
            raise
        except Exception as e:  # urllib3 connection errors, ApiException, timeouts
            raise ClusterUnavailable(f"Kubernetes API unreachable: {e.__class__.__name__}: {e}"[:400]) from e

    # ---- health -------------------------------------------------------
    async def _tool(self, cid: str, name: str, argv: list[str], parse) -> ComponentHealth:
        res = await run(*argv)
        if res.missing:
            return ComponentHealth(id=cid, name=name, status="missing", message=f"{name} is not installed",
                                   remediation="Run `make prereqs`")
        if not res.ok:
            return ComponentHealth(id=cid, name=name, status="error", message=(res.stderr or "failed")[:300])
        return ComponentHealth(id=cid, name=name, status="ok", version=parse(res.stdout), message="Installed")

    async def _kind_cluster(self) -> ComponentHealth:
        res = await run("kind", "get", "clusters")
        if res.missing:
            return ComponentHealth(id="kind", name="kind", status="missing", message="kind is not installed",
                                   remediation="Run `make prereqs`")
        ver = await run("kind", "version")
        version = ver.stdout.split()[1].lstrip("v") if ver.ok and len(ver.stdout.split()) > 1 else None
        if not res.ok:
            return ComponentHealth(id="kind", name="kind", status="warning", version=version,
                                   message="Can't list kind clusters (is Colima running?)",
                                   remediation="Run `make up`", details={"output": res.stderr[:300]})
        if settings.cluster_name in res.stdout.split():
            return ComponentHealth(id="kind", name="kind", status="ok", version=version,
                                   message=f"Cluster '{settings.cluster_name}' exists")
        return ComponentHealth(id="kind", name="kind", status="warning", version=version,
                               message=f"Cluster '{settings.cluster_name}' not found", remediation="Run `make up`")

    def _api_health(self) -> ComponentHealth:
        try:
            api = self._api()
            info = self._call(client.VersionApi(api).get_code)
            return ComponentHealth(id="kubernetes", name="Kubernetes API", status="ok",
                                   version=info.git_version.lstrip("v"),
                                   message=f"Context {settings.kube_context} reachable")
        except ClusterUnavailable as e:
            return ComponentHealth(id="kubernetes", name="Kubernetes API", status="warning", message=str(e),
                                   remediation="Run `make up`")

    async def health(self) -> list[ComponentHealth]:
        return list(await asyncio.gather(
            self._kind_cluster(),
            self._tool("kubectl", "kubectl", ["kubectl", "version", "--client", "-o", "json"],
                       lambda o: json.loads(o)["clientVersion"]["gitVersion"].lstrip("v")),
            self._tool("helm", "Helm", ["helm", "version", "--short"], lambda o: o.split("+")[0].lstrip("v")),
            asyncio.to_thread(self._api_health),
        ))

    # ---- reads --------------------------------------------------------
    def summary(self) -> dict:
        try:
            api = self._api()
            core, apps = client.CoreV1Api(api), client.AppsV1Api(api)
            version = self._call(client.VersionApi(api).get_code).git_version
            nodes = self._call(core.list_node).items
            namespaces = self._call(core.list_namespace).items
            pods = self._call(core.list_pod_for_all_namespaces).items
            deployments = self._call(apps.list_deployment_for_all_namespaces).items
        except ClusterUnavailable as e:
            return {"connected": False, "reason": str(e), "context": settings.kube_context}
        return {
            "connected": True,
            "context": settings.kube_context,
            "server_version": version,
            "nodes": {
                "total": len(nodes),
                "ready": sum(_ready(n) for n in nodes),
                "items": [
                    {
                        "name": n.metadata.name,
                        "ready": _ready(n),
                        "roles": sorted(k.split("/", 1)[1] for k in (n.metadata.labels or {})
                                        if k.startswith("node-role.kubernetes.io/")) or ["worker"],
                        "version": n.status.node_info.kubelet_version,
                        "arch": n.status.node_info.architecture,
                    }
                    for n in nodes
                ],
            },
            "namespaces": len(namespaces),
            "pods": {"total": len(pods), "by_phase": dict(Counter(p.status.phase for p in pods))},
            "deployments": {
                "total": len(deployments),
                "available": sum((d.status.available_replicas or 0) >= (d.spec.replicas or 0)
                                 for d in deployments),
            },
        }

    def pods(self, namespace: str | None = None) -> list[dict]:
        core = client.CoreV1Api(self._api())
        items = (self._call(core.list_namespaced_pod, namespace) if namespace
                 else self._call(core.list_pod_for_all_namespaces)).items
        now = datetime.now(UTC)
        out = []
        for p in items:
            statuses = p.status.container_statuses or []
            reason = next((s.state.waiting.reason for s in statuses if s.state and s.state.waiting), None) or \
                next((s.state.terminated.reason for s in statuses if s.state and s.state.terminated), None)
            created = p.metadata.creation_timestamp
            out.append({
                "namespace": p.metadata.namespace,
                "name": p.metadata.name,
                "phase": p.status.phase,
                "status": reason or p.status.phase,
                "ready": f"{sum(bool(s.ready) for s in statuses)}/{len(p.spec.containers)}",
                "restarts": sum(s.restart_count for s in statuses),
                "node": p.spec.node_name,
                "age_seconds": int((now - created).total_seconds()) if created else None,
            })
        return out
