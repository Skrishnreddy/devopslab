"""Phase 3: Kubernetes explorer shaping, API error pass-through, live logs, lab start/stop."""
import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from kubernetes import client

from app.providers import explorer as ex
from app.providers import registry
from app.providers.cluster import ClusterAPIError, KindCluster
from app.providers.lab_ops import LabOperations

AGO = datetime.now(UTC) - timedelta(minutes=10)


def meta(name, ns=None, labels=None):
    return NS(name=name, namespace=ns, labels=labels, creation_timestamp=AGO)


def test_deployment_row_matches_kubectl_columns():
    d = NS(metadata=meta("web", "shop"),
           spec=NS(replicas=3, template=NS(spec=NS(containers=[NS(image="nginx:1.27")]))),
           status=NS(ready_replicas=2, updated_replicas=3, available_replicas=2))
    row = ex.deployment_row(d)
    assert row["ready"] == "2/3" and row["up_to_date"] == 3 and row["available"] == 2
    assert row["images"] == ["nginx:1.27"] and row["healthy"] is False
    assert 590 <= row["age_seconds"] <= 610


def test_service_row_ports_and_external_ip():
    s = NS(metadata=meta("api", "shop"),
           spec=NS(type="NodePort", cluster_ip="10.96.0.10", external_i_ps=None, selector={"app": "api"},
                   ports=[NS(port=80, node_port=30080, protocol="TCP"), NS(port=443, node_port=None, protocol="TCP")]),
           status=NS(load_balancer=NS(ingress=None)))
    row = ex.service_row(s)
    assert row["ports"] == "80:30080/TCP,443/TCP" and row["external_ip"] is None
    lb = NS(metadata=meta("lb", "shop"),
            spec=NS(type="LoadBalancer", cluster_ip="10.96.0.11", external_i_ps=None, selector=None, ports=[]),
            status=NS(load_balancer=NS(ingress=None)))
    assert ex.service_row(lb)["external_ip"] == "<pending>" and ex.service_row(lb)["ports"] == "<none>"


def test_event_row():
    e = NS(metadata=meta("x", "shop"), type="Warning", reason="BackOff", message=" Back-off restarting \n",
           count=7, last_timestamp=AGO, event_time=None, first_timestamp=None,
           involved_object=NS(kind="Pod", name="web-1"))
    assert ex.event_row(e) | {"last_seen_seconds": 0} == {
        "namespace": "shop", "type": "Warning", "reason": "BackOff", "object": "Pod/web-1",
        "message": "Back-off restarting", "count": 7, "last_seen_seconds": 0}


def test_pod_detail_explains_crashloop():
    waiting = NS(running=None, waiting=NS(reason="CrashLoopBackOff", message="back-off 5m0s"), terminated=None)
    last = NS(running=None, waiting=None, terminated=NS(reason="Error", exit_code=1, message=None))
    p = NS(metadata=meta("web-1", "shop", {"app": "web"}),
           spec=NS(node_name="w1", service_account_name="default",
                   containers=[NS(name="web", image="web:1", ports=[NS(container_port=8080, protocol="TCP")],
                                  resources=NS(requests={"cpu": "100m"}, limits=None))]),
           status=NS(phase="Running", pod_ip="10.244.1.5", conditions=[NS(type="Ready", status="False",
                                                                          reason="ContainersNotReady", message=None)],
                     container_statuses=[NS(name="web", ready=False, restart_count=5, state=waiting,
                                            last_state=last)]))
    d = ex.pod_detail(p, [])
    c = d["containers"][0]
    assert c["state"] == "CrashLoopBackOff" and c["last_state"] == "Error"
    assert c["last_state_detail"] == "exit code 1" and c["restarts"] == 5
    assert c["ports"] == ["8080/TCP"] and c["requests"] == {"cpu": "100m"}


def test_yaml_drops_noise_and_never_offers_secrets():
    pod = client.V1Pod(api_version="v1", kind="Pod", metadata=client.V1ObjectMeta(
        name="p", namespace="n", managed_fields=[client.V1ManagedFieldsEntry(manager="kubectl")],
        annotations={"kubectl.kubernetes.io/last-applied-configuration": "{...}"}))
    out = ex.to_yaml(pod)
    assert "managedFields" not in out and "last-applied" not in out and "name: p" in out
    assert "secret" not in ex.KINDS
    with pytest.raises(ClusterAPIError):
        KindCluster().yaml("secret", "kube-system", "x")


class FakeCluster:
    def __init__(self):
        self.calls = []

    def deployments(self, ns):
        self.calls.append(ns)
        return [{"name": "web"}]

    def pod(self, ns, name):
        raise ClusterAPIError(404, f'pods "{name}" not found')

    def events(self, ns, limit):
        raise ClusterAPIError(500, "etcdserver: request timed out")

    def follow_logs(self, ns, name, container, tail):
        return FakeResp([b"line one\nline ", b"two\n", b"partial"])


class FakeResp:
    def __init__(self, chunks):
        self.chunks, self.closed = chunks, False

    def stream(self, *_a, **_k):
        yield from self.chunks

    def close(self):
        self.closed = True

    def release_conn(self):
        pass


@pytest.fixture()
def fake_cluster(monkeypatch):
    fc = FakeCluster()
    monkeypatch.setattr(registry, "cluster", lambda: fc)
    return fc


def test_lists_pass_namespace(authed, fake_cluster):
    assert authed.get("/api/v1/cluster/deployments", params={"namespace": "shop"}).json() == [{"name": "web"}]
    assert fake_cluster.calls == ["shop"]


def test_api_errors_are_shown_verbatim(authed, fake_cluster):
    r = authed.get("/api/v1/cluster/pods/shop/nope")
    assert r.status_code == 404
    assert r.json()["error"] == {"code": "kubernetes_error", "message": 'pods "nope" not found',
                                 "detail": {"status": 404}}
    r = authed.get("/api/v1/cluster/events")
    assert r.status_code == 502 and r.json()["error"]["message"] == "etcdserver: request timed out"


def test_bad_names_rejected(authed, fake_cluster):
    assert authed.get("/api/v1/cluster/pods/Shop/x").status_code == 422
    assert authed.get("/api/v1/cluster/pods/shop/x/logs", params={"container": "a;b"}).status_code == 422


def test_explorer_without_cluster_is_503(authed):
    for path in ("namespaces", "deployments", "services", "events"):
        r = authed.get(f"/api/v1/cluster/{path}")
        assert r.status_code == 503 and r.json()["error"]["code"] == "cluster_unreachable"


def test_follow_logs_streams_lines_then_end(authed, fake_cluster):
    with authed.stream("GET", "/api/v1/cluster/pods/shop/web-1/logs", params={"follow": "true"}) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    assert [e.get("line") for e in events[:3]] == ["line one", "line two", "partial"]
    assert "end" in events[-1]


def test_lab_start_runs_the_script_and_reports_failure(authed, monkeypatch):
    ops = LabOperations({"start": ["sh", "-c", "echo '\x1b[1;36m==>\x1b[0m starting'; echo boom >&2; exit 3"],
                         "stop": ["true"]})
    monkeypatch.setattr(registry, "lab_ops", lambda: ops)
    r = authed.post("/api/v1/lab/start")
    assert r.status_code == 202 and r.json()["state"] == "running"
    for _ in range(50):
        op = authed.get("/api/v1/lab/operation").json()
        if op["state"] != "running":
            break
        asyncio.run(asyncio.sleep(0.05))
    assert op["state"] == "failed" and op["exit_code"] == 3
    assert op["output"] == ["==> starting", "boom"]
    assert authed.post("/api/v1/lab/reboot").status_code == 404


def test_lab_actions_need_login_and_origin(client):
    assert client.post("/api/v1/lab/start").status_code == 401


class BlockingResp:
    """Like urllib3: stream() holds a lock while blocked in recv(); close() needs that lock."""

    def __init__(self):
        import threading
        self.lock, self.wake, self.order = threading.Lock(), threading.Event(), []

    def stream(self, *_a, **_k):
        with self.lock:
            self.wake.wait(10)
        return iter(())

    def shutdown(self):
        self.order.append("shutdown")
        self.wake.set()

    def close(self):
        with self.lock:
            self.order.append("close")

    def release_conn(self):
        self.order.append("release")


def test_stopping_a_follow_stream_never_blocks_the_event_loop():
    from app.api.v1.cluster import stop_stream

    async def run():
        resp = BlockingResp()
        reader = asyncio.ensure_future(asyncio.to_thread(lambda: list(resp.stream())))
        await asyncio.sleep(0.05)  # reader is now blocked holding the lock
        ticks = 0

        async def heartbeat():
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0.01)

        hb = asyncio.create_task(heartbeat())
        await asyncio.wait_for(stop_stream(resp, reader), timeout=3)
        hb.cancel()
        return resp, ticks

    resp, ticks = asyncio.run(run())
    assert resp.order[0] == "shutdown" and "release" in resp.order
    assert ticks > 0  # the loop kept running


def test_yaml_timestamps_look_like_kubectl():
    pod = client.V1Pod(api_version="v1", kind="Pod",
                       metadata=client.V1ObjectMeta(name="p", creation_timestamp=datetime(2026, 11, 19, 9, 10, 45,
                                                                                          tzinfo=UTC)))
    assert "creationTimestamp: 2026-11-19T09:10:45Z" in ex.to_yaml(pod)
