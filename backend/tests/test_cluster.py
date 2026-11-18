from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

from app.providers import cluster as cluster_mod


def test_summary_without_cluster_says_so(authed):
    body = authed.get("/api/v1/cluster/summary").json()
    assert body["connected"] is False and "make up" in body["reason"]


def test_pods_without_cluster_is_503_with_reason(authed):
    r = authed.get("/api/v1/cluster/pods")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "cluster_unreachable"


def test_bad_namespace_rejected(authed):
    assert authed.get("/api/v1/cluster/pods", params={"namespace": "../x"}).status_code == 422


def _node(name, ready, role=None):
    labels = {f"node-role.kubernetes.io/{role}": ""} if role else {}
    return NS(metadata=NS(name=name, labels=labels),
              status=NS(conditions=[NS(type="Ready", status="True" if ready else "False")],
                        node_info=NS(kubelet_version="v1.31.4", architecture="arm64")))


def _pod(ns, name, phase, ready, waiting=None, restarts=0):
    state = NS(waiting=NS(reason=waiting) if waiting else None, terminated=None)
    return NS(metadata=NS(namespace=ns, name=name, creation_timestamp=datetime.now(UTC) - timedelta(minutes=5)),
              status=NS(phase=phase, container_statuses=[NS(ready=ready, restart_count=restarts, state=state)]),
              spec=NS(containers=[1], node_name="w1"))


def test_summary_counts_come_from_the_api(monkeypatch):
    nodes = [_node("cp", True, "control-plane"), _node("w1", True), _node("w2", False)]
    pods = [_pod("a", "p1", "Running", True), _pod("a", "p2", "Running", False, "CrashLoopBackOff", 4),
            _pod("b", "p3", "Pending", False)]
    deps = [NS(spec=NS(replicas=2), status=NS(available_replicas=2)),
            NS(spec=NS(replicas=1), status=NS(available_replicas=None))]

    class Core:
        def __init__(self, _):
            pass

        def list_node(self, **_):
            return NS(items=nodes)

        def list_namespace(self, **_):
            return NS(items=[1, 2, 3, 4])

        def list_pod_for_all_namespaces(self, **_):
            return NS(items=pods)

    class Apps:
        def __init__(self, _):
            pass

        def list_deployment_for_all_namespaces(self, **_):
            return NS(items=deps)

    class Version:
        def __init__(self, _):
            pass

        def get_code(self, **_):
            return NS(git_version="v1.31.4")

    monkeypatch.setattr(cluster_mod.KindCluster, "_api", lambda self: object())
    monkeypatch.setattr(cluster_mod.client, "CoreV1Api", Core)
    monkeypatch.setattr(cluster_mod.client, "AppsV1Api", Apps)
    monkeypatch.setattr(cluster_mod.client, "VersionApi", Version)
    k = cluster_mod.KindCluster()
    s = k.summary()
    assert s["connected"] and s["server_version"] == "v1.31.4"
    assert s["nodes"]["total"] == 3 and s["nodes"]["ready"] == 2
    assert s["nodes"]["items"][0]["roles"] == ["control-plane"] and s["nodes"]["items"][1]["roles"] == ["worker"]
    assert s["namespaces"] == 4
    assert s["pods"] == {"total": 3, "by_phase": {"Running": 2, "Pending": 1}}
    assert s["deployments"] == {"total": 2, "available": 1}
    p = k.pods()
    assert p[1]["status"] == "CrashLoopBackOff" and p[1]["ready"] == "0/1" and p[1]["restarts"] == 4
    assert 290 < p[0]["age_seconds"] < 310
