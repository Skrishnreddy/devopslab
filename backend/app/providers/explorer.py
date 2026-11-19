"""Read-only Kubernetes explorer (Phase 3): shapes API objects for the UI.

Every function takes objects straight from the kubernetes client; nothing is
cached or invented. Columns follow `kubectl get` so the two can be compared.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

import yaml
from kubernetes import client

_UTC_TS = re.compile(r"'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\+00:00'")
KINDS = {"pod", "deployment", "service", "namespace", "configmap", "node"}  # YAML view; never Secrets


def _age(ts) -> int | None:
    return int((datetime.now(UTC) - ts).total_seconds()) if ts else None


def namespace_row(n) -> dict:
    labels = n.metadata.labels or {}
    return {"name": n.metadata.name, "status": n.status.phase, "age_seconds": _age(n.metadata.creation_timestamp),
            "lab": labels.get("devopslab.io/resettable") == "true",
            "managed": labels.get("devopslab.io/managed") == "true"}


def deployment_row(d) -> dict:
    st = d.status
    want = d.spec.replicas if d.spec.replicas is not None else 1
    return {
        "namespace": d.metadata.namespace, "name": d.metadata.name,
        "ready": f"{st.ready_replicas or 0}/{want}",
        "up_to_date": st.updated_replicas or 0, "available": st.available_replicas or 0,
        "age_seconds": _age(d.metadata.creation_timestamp),
        "images": [c.image for c in d.spec.template.spec.containers],
        "healthy": (st.available_replicas or 0) >= want,
    }


def _port(p) -> str:
    s = f"{p.port}"
    if p.node_port:
        s += f":{p.node_port}"
    return f"{s}/{p.protocol}"


def service_row(s) -> dict:
    spec = s.spec
    ingress = (s.status.load_balancer.ingress or []) if s.status and s.status.load_balancer else []
    external = ",".join(i.ip or i.hostname for i in ingress) or ",".join(spec.external_i_ps or []) or None
    return {
        "namespace": s.metadata.namespace, "name": s.metadata.name, "type": spec.type,
        "cluster_ip": spec.cluster_ip,
        "external_ip": external or ("<pending>" if spec.type == "LoadBalancer" else None),
        "ports": ",".join(_port(p) for p in spec.ports or []) or "<none>",
        "selector": spec.selector or {}, "age_seconds": _age(s.metadata.creation_timestamp),
    }


def event_row(e) -> dict:
    last = e.last_timestamp or e.event_time or e.first_timestamp or e.metadata.creation_timestamp
    obj = e.involved_object
    return {
        "namespace": e.metadata.namespace, "type": e.type, "reason": e.reason,
        "object": f"{obj.kind}/{obj.name}", "message": (e.message or "").strip(),
        "count": e.count or 1, "last_seen_seconds": _age(last),
    }


def _state(st) -> tuple[str, str | None]:
    if st is None:
        return "Unknown", None
    if st.running:
        return "Running", None
    if st.waiting:
        return st.waiting.reason or "Waiting", st.waiting.message
    if st.terminated:
        t = st.terminated
        return t.reason or "Terminated", f"exit code {t.exit_code}" + (f": {t.message}" if t.message else "")
    return "Unknown", None


def pod_detail(p, events: list) -> dict:
    statuses = {s.name: s for s in (p.status.container_statuses or [])}
    containers = []
    for c in p.spec.containers:
        s = statuses.get(c.name)
        state, detail = _state(s.state if s else None)
        last, last_detail = _state(s.last_state) if s and s.last_state and (
            s.last_state.terminated or s.last_state.waiting) else (None, None)
        containers.append({
            "name": c.name, "image": c.image, "ready": bool(s and s.ready),
            "restarts": s.restart_count if s else 0, "state": state, "state_detail": detail,
            "last_state": last, "last_state_detail": last_detail,
            "ports": [f"{cp.container_port}/{cp.protocol}" for cp in c.ports or []],
            "requests": (c.resources.requests or {}) if c.resources else {},
            "limits": (c.resources.limits or {}) if c.resources else {},
        })
    return {
        "namespace": p.metadata.namespace, "name": p.metadata.name, "phase": p.status.phase,
        "node": p.spec.node_name, "pod_ip": p.status.pod_ip, "service_account": p.spec.service_account_name,
        "labels": p.metadata.labels or {}, "age_seconds": _age(p.metadata.creation_timestamp),
        "conditions": [{"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
                       for c in p.status.conditions or []],
        "containers": containers,
        "events": [event_row(e) for e in events],
    }


def to_yaml(obj) -> str:
    """kubectl-style YAML without the noise (managedFields, last-applied annotation)."""
    data = client.ApiClient().sanitize_for_serialization(obj)
    meta = data.get("metadata", {})
    meta.pop("managedFields", None)
    (meta.get("annotations") or {}).pop("kubectl.kubernetes.io/last-applied-configuration", None)
    if meta.get("annotations") == {}:
        meta.pop("annotations")
    out = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    return _UTC_TS.sub(r"\1Z", out)  # kubectl style: 2026-11-19T09:10:45Z
