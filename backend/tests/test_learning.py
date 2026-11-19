"""Learning engine: lesson content, checks against a fake API server, exercise ops and the lesson API."""
import pytest

from app.content.loader import ContentError, get_content, load
from app.content.models import Check, Exercise
from app.learning import exercises as ex_ops
from app.learning.checks import CheckRunner, resolve
from app.providers import registry
from app.providers.cluster import ClusterAPIError, ClusterUnavailable

NS = "/api/v1/namespaces/lab-playground/"
APPS = "/apis/apps/v1/namespaces/lab-playground/"


def pod(name, labels, *, ready=True, waiting=None, image="nginx:1.27-alpine"):
    state = {"waiting": {"reason": waiting}} if waiting else {"running": {}}
    return {"metadata": {"name": name, "labels": labels}, "spec": {"containers": [{"name": "c", "image": image}]},
            "status": {"phase": "Pending" if waiting else "Running",
                       "containerStatuses": [{"ready": ready and not waiting, "state": state}]}}


class FakeAPI:
    def __init__(self, objects=None):
        self.objects = objects or {}
        self.calls = []

    def __call__(self, path, params):
        self.calls.append((path, params))
        if path == NS + "pods" and params:
            want = dict(kv.split("=") for kv in params["labelSelector"].split(","))
            items = [o for p, o in self.objects.items() if p.startswith(NS + "pods/")
                     and want.items() <= o["metadata"]["labels"].items()]
            return {"items": items}
        if path in self.objects:
            return self.objects[path]
        raise ClusterAPIError(404, f"{path} not found")


def run(check, objects):
    return CheckRunner(FakeAPI(objects)).run(Check(**check))


def test_resolve_paths():
    obj = {"spec": {"containers": [{"image": "a"}, {"image": "b"}], "selector": {"app": "x"}}}
    assert resolve(obj, "spec.containers[1].image") == "b"
    assert resolve(obj, "spec.selector.app") == "x"
    assert resolve(obj, "spec.containers[5].image") is not None and resolve(obj, "spec.nope") is not obj


def test_field_check_reports_what_it_saw():
    objs = {APPS + "deployments/shop": {"spec": {"replicas": 2}}}
    r = run({"type": "field", "description": "d", "kind": "Deployment", "name": "shop", "path": "spec.replicas",
             "equals": 3}, objs)
    assert r == {"description": "d", "passed": False, "observed": "spec.replicas = 2"}
    r = run({"type": "field", "description": "d", "kind": "Deployment", "name": "gone", "path": "spec.replicas",
             "equals": 3}, objs)
    assert not r["passed"] and "not found in lab-playground" in r["observed"]


def test_pods_ready_counts_and_names_broken_pods():
    objs = {NS + "pods/a": pod("a", {"app": "cache"}),
            NS + "pods/b": pod("b", {"app": "cache"}, waiting="ImagePullBackOff"),
            NS + "pods/c": pod("c", {"app": "other"})}
    check = {"type": "pods_ready", "description": "d", "selector": {"app": "cache"}, "min": 1}
    assert run(check, objs)["passed"]
    r = run({**check, "all_ready": True}, objs)
    assert not r["passed"] and r["observed"] == "1 of 2 pods with app=cache ready: a (Running), b (ImagePullBackOff)"


def test_rollout_ready():
    d = {"metadata": {"generation": 2}, "spec": {"replicas": 2},
         "status": {"observedGeneration": 2, "replicas": 3, "readyReplicas": 2, "updatedReplicas": 1}}
    check = {"type": "rollout_ready", "description": "d", "name": "catalog"}
    assert not run(check, {APPS + "deployments/catalog": d})["passed"]
    d["status"].update(replicas=2, updatedReplicas=2)
    assert run(check, {APPS + "deployments/catalog": d}) == {"description": "d", "passed": True,
                                                            "observed": "ready 2/2, up to date 2/2"}


def test_endpoints():
    ep = {"subsets": [{"addresses": [{"ip": "1"}], "notReadyAddresses": [{"ip": "2"}]}]}
    r = run({"type": "endpoints", "description": "d", "name": "orders", "min": 2}, {NS + "endpoints/orders": ep})
    assert not r["passed"] and r["observed"] == "1 ready endpoint address(es), 1 not ready"


def test_answer_compares_with_the_real_cluster_without_revealing_it():
    nodes = {"items": [{"metadata": {"name": "control-1", "labels": {"node-role.kubernetes.io/control-plane": ""}}},
                       {"metadata": {"name": "w1", "labels": {}}}, {"metadata": {"name": "w2", "labels": {}}}]}
    objs = {"/api/v1/nodes": nodes, NS + "configmaps/facts": {"data": {"nodes": " 3\n", "cp": "w1"}}}
    ok = run({"type": "answer", "description": "d", "name": "facts", "key": "nodes", "source": "node_count"}, objs)
    assert ok["passed"]
    bad = run({"type": "answer", "description": "d", "name": "facts", "key": "cp", "source": "control_plane_node"},
              objs)
    assert not bad["passed"] and bad["observed"] == "you answered cp='w1'"  # the right node is never shown


def test_api_errors_are_shown_and_unreachable_cluster_propagates():
    def forbidden(path, params):
        raise ClusterAPIError(403, 'pods is forbidden: User "x" cannot list')

    r = CheckRunner(forbidden).run(Check(type="pods_ready", description="d", selector={"app": "x"}))
    assert not r["passed"] and r["observed"].startswith("Kubernetes API error: pods is forbidden")

    def down(path, params):
        raise ClusterUnavailable("Kubernetes API unreachable")

    with pytest.raises(ClusterUnavailable):
        CheckRunner(down).run(Check(type="pods_ready", description="d", selector={"app": "x"}))


# ---- content ------------------------------------------------------------------
def test_first_five_kubernetes_modules_have_full_lessons():
    c = load()
    k8s = next(t for t in c.tracks if t.id == "kubernetes")
    first5 = [m.id for m in sorted(k8s.modules, key=lambda m: m.order)[:5]]
    assert sorted(c.lessons) == sorted(first5)
    for lesson in c.lessons.values():
        assert lesson.concept and lesson.use_case and lesson.architecture and lesson.commands
        assert all(e.expected_output and e.solution for e in lesson.exercises)
        assert {e.kind for e in lesson.exercises} == {"practice", "troubleshooting"}
        assert all(len(q.options) == 4 for q in lesson.quiz)


def test_every_check_targets_something_the_exercise_cleans_up():
    """Reset must remove everything an exercise asks the learner to create."""
    for lesson in load().lessons.values():
        for e in lesson.exercises:
            cleaned = {(r.kind, r.name) for r in e.cleanup}
            for c in e.checks:
                if c.kind and c.name and c.type != "absent":
                    assert (c.kind, c.name) in cleaned, (lesson.id, e.id, c.kind, c.name)


def _write_content(tmp_path, lesson_yaml):
    import shutil

    from app.core.config import settings
    root = tmp_path / "content"
    shutil.copytree(settings.content_dir, root, ignore=shutil.ignore_patterns("lessons"))
    (root / "lessons").mkdir()
    (root / "lessons" / "x.yaml").write_text(lesson_yaml)
    return root


BASE = """id: k8s-02-pods
concept: c
use_case: u
architecture: a
commands: [{command: kubectl get pods, explanation: e}]
quiz:
  - {question: q, options: [a, b], answer: 0, explanation: e}
  - {question: q, options: [a, b], answer: 1, explanation: e}
  - {question: q, options: [a, b], answer: 0, explanation: e}
exercises:
  - id: tx
    title: t
    kind: troubleshooting
    instructions: i
    solution: s
    checks: [{type: exists, description: d, kind: Pod, name: x}]
"""


@pytest.mark.parametrize("extra, error", [
    ("    setup: |\n      kind: ClusterRoleBinding\n      metadata: {name: x}\n", "setup kind must be one of"),
    ("    setup: |\n      kind: Pod\n      metadata: {name: x, namespace: kube-system}\n", "must not set a namespace"),
    ("    setup: |\n      kind: Pod\n      metadata: {name: x}\n", "must be in cleanup"),
])
def test_unsafe_setup_is_rejected(tmp_path, extra, error):
    with pytest.raises(ContentError, match=error):
        load(_write_content(tmp_path, BASE + extra))


def test_lesson_needs_a_module_and_a_troubleshooting_exercise(tmp_path):
    with pytest.raises(ContentError, match="no matching module"):
        load(_write_content(tmp_path / "a", BASE.replace("id: k8s-02-pods", "id: k8s-99-nope")))
    with pytest.raises(ContentError, match="troubleshooting exercise"):
        load(_write_content(tmp_path / "b", BASE.replace("kind: troubleshooting", "kind: practice")))


# ---- exercise ops ---------------------------------------------------------------
def test_setup_forces_the_namespace_and_reset_deletes_then_reapplies():
    calls = []

    def kubectl(*args, stdin=None, **_):
        calls.append((args, stdin))
        return "pod/shop created\n"

    e = Exercise(id="bad", title="t", instructions="i", solution="s", kind="troubleshooting",
                 setup="kind: Pod\nmetadata: {name: shop}\nspec: {containers: [{name: c, image: x}]}\n",
                 checks=[Check(type="exists", description="d", kind="Pod", name="shop")],
                 cleanup=[{"kind": "Pod", "name": "shop"}])
    out = ex_ops.reset(e, kubectl)
    assert calls[0][0][:4] == ("delete", "pod/shop", "-n", "lab-playground")
    assert calls[1][0][:3] == ("apply", "-n", "lab-playground")
    assert "namespace: lab-playground" in calls[1][1] and "devopslab.io/exercise: bad" in calls[1][1]
    assert out[-1] == "pod/shop created"


# ---- API -----------------------------------------------------------------------
class FakeCluster:
    def __init__(self, objects):
        self.raw_get = FakeAPI(objects)


@pytest.fixture()
def cluster(monkeypatch):
    objs = {}
    monkeypatch.setattr(registry, "cluster", lambda: FakeCluster(objs))
    return objs


def test_lesson_hides_answers_and_solutions(authed):
    body = authed.get("/api/v1/learn/modules/k8s-02-pods").json()
    assert body["status"] == "not_started" and body["namespace"] == "lab-playground"
    assert body["lesson"]["concept"] and body["exercises"][0]["checks"][0] == "Pod web is Running and Ready"
    assert all("answer" not in q and "explanation" not in q for q in body["quiz"]["questions"])
    assert all("solution" not in e and "setup" not in e for e in body["exercises"])
    assert authed.get("/api/v1/learn/modules/k8s-02-pods/exercises/first-pod/solution").json()["solution"]
    assert authed.get("/api/v1/learn/modules/k8s-20-production-support").status_code == 404
    assert authed.get("/api/v1/learn/modules/nope").status_code == 404
    tracks = authed.get("/api/v1/learn/tracks").json()
    mods = {m["id"]: m["lesson"] for t in tracks for m in t["modules"]}
    assert mods["k8s-02-pods"] is True and mods["k8s-06-ingress"] is False


def test_checks_record_attempts_and_complete_the_module(authed, cluster):
    url = "/api/v1/learn/modules/k8s-02-pods"
    r = authed.post(f"{url}/exercises/first-pod/check").json()
    assert r["passed"] is False and r["module_status"] == "started"
    assert r["results"][0]["observed"].startswith("0 of 0 pods")
    cluster[NS + "pods/web"] = pod("web", {"app": "web"})
    assert authed.post(f"{url}/exercises/first-pod/check").json()["passed"] is True
    cluster[NS + "pods/shop"] = pod("shop", {"app": "shop"})
    assert authed.post(f"{url}/exercises/bad-image/check").json()["module_status"] == "started"  # quiz left
    wrong = authed.post(f"{url}/quiz", json={"answers": [0, 0, 0, 1]}).json()
    assert wrong["passed"] is False and wrong["score"] == 0 and wrong["results"][0]["explanation"]
    right = authed.post(f"{url}/quiz", json={"answers": [1, 2, 1, 0]}).json()
    assert right["percent"] == 100 and right["module_status"] == "completed"
    view = authed.get(url).json()
    assert view["status"] == "completed" and view["quiz"]["best_percent"] == 100
    assert view["exercises"][0]["passed"] and view["exercises"][0]["last"]["results"][0]["passed"]
    assert authed.post(f"{url}/quiz", json={"answers": [1]}).status_code == 422
    titles = [a["title"] for a in authed.get("/api/v1/activity/recent").json()]
    assert "Kubernetes: Pods completed" in titles


def test_check_needs_a_cluster(authed, monkeypatch):
    class Down:
        def raw_get(self, *a):
            raise ClusterUnavailable("No kubeconfig at ~/.kube/devopslab. Run `make up`.")

    monkeypatch.setattr(registry, "cluster", lambda: Down())
    r = authed.post("/api/v1/learn/modules/k8s-02-pods/exercises/first-pod/check")
    assert r.status_code == 503 and "make up" in r.json()["error"]["message"]


def test_setup_and_reset_report_kubectl_errors(authed, monkeypatch):
    from app.providers.labs import LabError

    def boom(*a, **k):
        raise LabError('namespaces "lab-playground" not found', "set up")

    monkeypatch.setattr(ex_ops, "kubectl", boom)
    monkeypatch.setattr(ex_ops.setup, "__defaults__", (boom,))
    monkeypatch.setattr(ex_ops.reset, "__defaults__", (boom,))
    r = authed.post("/api/v1/learn/modules/k8s-02-pods/exercises/bad-image/setup")
    assert r.status_code == 502 and 'lab-playground" not found' in r.json()["error"]["message"]
    assert authed.post("/api/v1/learn/modules/k8s-02-pods/exercises/first-pod/setup").status_code == 409
    assert authed.post("/api/v1/learn/modules/k8s-02-pods/exercises/first-pod/reset").status_code == 502


def test_learning_needs_a_session(client):
    assert client.get("/api/v1/learn/modules/k8s-02-pods").status_code == 401
    assert client.post("/api/v1/learn/modules/k8s-02-pods/exercises/first-pod/check").status_code == 401


def test_content_is_cached_with_lessons():
    assert "k8s-01-architecture" in get_content().lessons
