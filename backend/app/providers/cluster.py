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
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

from ..core.config import settings
from . import explorer as ex
from .commands import run
from .health import ComponentHealth

TIMEOUT = 4


class ClusterUnavailable(Exception):
    pass


class ClusterAPIError(Exception):
    """The API server answered with an error (404, 403, ...). Shown to the learner verbatim."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _api_error(e: ApiException) -> ClusterAPIError:
    try:
        message = json.loads(e.body).get("message") or e.reason
    except (TypeError, ValueError):
        message = e.body or e.reason
    return ClusterAPIError(e.status, str(message))


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
        except ApiException as e:
            if e.status:
                raise _api_error(e) from e
            raise ClusterUnavailable(f"Kubernetes API unreachable: {e.reason}"[:400]) from e
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
        # kind talks to whatever Docker context is current; pin it to the lab's Colima
        # profile so the result doesn't depend on the user's global context.
        res = await run("kind", "get", "clusters", env={"DOCKER_CONTEXT": settings.docker_context})
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

    # ---- explorer (Phase 3) ------------------------------------------
    def _apis(self):
        api = self._api()
        return client.CoreV1Api(api), client.AppsV1Api(api)

    def namespaces(self) -> list[dict]:
        core, _ = self._apis()
        return [ex.namespace_row(n) for n in self._call(core.list_namespace).items]

    def deployments(self, namespace: str | None = None) -> list[dict]:
        _, apps = self._apis()
        items = (self._call(apps.list_namespaced_deployment, namespace) if namespace
                 else self._call(apps.list_deployment_for_all_namespaces)).items
        return [ex.deployment_row(d) for d in items]

    def services(self, namespace: str | None = None) -> list[dict]:
        core, _ = self._apis()
        items = (self._call(core.list_namespaced_service, namespace) if namespace
                 else self._call(core.list_service_for_all_namespaces)).items
        return [ex.service_row(s) for s in items]

    def events(self, namespace: str | None = None, limit: int = 200) -> list[dict]:
        core, _ = self._apis()
        items = (self._call(core.list_namespaced_event, namespace) if namespace
                 else self._call(core.list_event_for_all_namespaces)).items
        rows = sorted((ex.event_row(e) for e in items),
                      key=lambda r: r["last_seen_seconds"] if r["last_seen_seconds"] is not None else 10**9)
        return rows[:limit]

    def pod(self, namespace: str, name: str) -> dict:
        core, _ = self._apis()
        p = self._call(core.read_namespaced_pod, name, namespace)
        evs = self._call(core.list_namespaced_event, namespace,
                         field_selector=f"involvedObject.kind=Pod,involvedObject.name={name}").items
        evs.sort(key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp, reverse=True)
        return ex.pod_detail(p, evs)

    def yaml(self, kind: str, namespace: str | None, name: str) -> str:
        if kind not in ex.KINDS:
            raise ClusterAPIError(400, f"YAML view isn't available for {kind}")
        core, apps = self._apis()
        read = {
            "pod": lambda: self._call(core.read_namespaced_pod, name, namespace),
            "service": lambda: self._call(core.read_namespaced_service, name, namespace),
            "configmap": lambda: self._call(core.read_namespaced_config_map, name, namespace),
            "deployment": lambda: self._call(apps.read_namespaced_deployment, name, namespace),
            "namespace": lambda: self._call(core.read_namespace, name),
            "node": lambda: self._call(core.read_node, name),
        }[kind]
        obj = read()
        obj.kind = obj.kind or kind.capitalize()
        return ex.to_yaml(obj)

    def logs(self, namespace: str, name: str, container: str | None, tail: int, previous: bool = False) -> str:
        core, _ = self._apis()
        kw = {"tail_lines": tail, "timestamps": False, "previous": previous}
        if container:
            kw["container"] = container
        return self._call(core.read_namespaced_pod_log, name, namespace, **kw)

    def follow_logs(self, namespace: str, name: str, container: str | None, tail: int):
        """Open a follow stream. Returns the raw urllib3 response; the caller must release it."""
        core, _ = self._apis()
        kw = {"tail_lines": tail, "follow": True, "_preload_content": False}
        if container:
            kw["container"] = container
        try:
            return core.read_namespaced_pod_log(name, namespace, _request_timeout=(TIMEOUT, None), **kw)
        except ApiException as e:
            if e.status:
                raise _api_error(e) from e
            raise ClusterUnavailable(f"Kubernetes API unreachable: {e.reason}") from e
        except Exception as e:
            raise ClusterUnavailable(f"Kubernetes API unreachable: {e.__class__.__name__}: {e}"[:400]) from e

    def raw_get(self, path: str, params: dict[str, str] | None = None) -> dict:
        """GET an API path and return the JSON as-is (used by lesson checks)."""
        api = self._api()
        return self._call(api.call_api, path, "GET", query_params=list((params or {}).items()),
                          response_type="object", auth_settings=["BearerToken"], _return_http_data_only=True)

    def usage(self, namespaces: list[str]) -> dict:
        """Live CPU/memory from metrics-server plus quota usage, summed over a lab's namespaces."""
        api = self._api()
        core, custom = client.CoreV1Api(api), client.CustomObjectsApi(api)
        cpu_m = mem_mi = 0.0
        pods = 0
        metrics_error = None
        quota: dict[str, dict[str, str]] = {}
        for ns in namespaces:
            pods += len(self._call(core.list_namespaced_pod, ns).items)
            try:
                items = self._call(custom.list_namespaced_custom_object, "metrics.k8s.io", "v1beta1", ns, "pods")
                for pm in items.get("items", []):
                    for c in pm.get("containers", []):
                        cpu_m += ex.cpu_millicores(c["usage"]["cpu"])
                        mem_mi += ex.memory_mib(c["usage"]["memory"])
            except (ClusterAPIError, ClusterUnavailable) as e:
                metrics_error = f"metrics-server: {e}"
            for q in self._call(core.list_namespaced_resource_quota, ns).items:
                for k, hard in (q.status.hard or {}).items():
                    quota[k] = {"hard": hard, "used": (q.status.used or {}).get(k, "0")}
        return {"cpu_millicores": round(cpu_m), "memory_mib": round(mem_mi), "pods": pods,
                "quota": quota, "metrics_error": metrics_error}
