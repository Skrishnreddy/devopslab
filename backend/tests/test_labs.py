import pytest

from app.providers.labs import LabError, NamespaceLabProvisioner

NS = "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {name}\n  labels: {labels}\n"
RESETTABLE = '{"devopslab.io/resettable": "true"}'


@pytest.fixture()
def lab(tmp_path, monkeypatch):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "kustomization.yaml").write_text("resources: []\n")
    p = NamespaceLabProvisioner(tmp_path)
    calls, rendered = [], {"text": ""}

    def fake(*args, step, **_):
        calls.append(args)
        return rendered["text"] if args[0] == "kustomize" else "namespace/x configured\n"

    monkeypatch.setattr(p, "_kubectl", fake)
    return p, calls, rendered


def test_reset_only_deletes_resettable_namespaces(lab):
    p, calls, rendered = lab
    rendered["text"] = "---\n".join([
        NS.format(name="lab-demo", labels=RESETTABLE),
        NS.format(name="kube-system", labels=RESETTABLE),      # protected even if labelled
        NS.format(name="devopslab-system", labels=RESETTABLE),  # protected prefix
        NS.format(name="other", labels="{}"),
    ])
    out = p.reset("demo")
    assert out["reset_namespaces"] == ["lab-demo"]
    assert [c[2] for c in calls if c[0] == "delete"] == ["lab-demo"]


def test_reset_refuses_when_nothing_is_resettable(lab):
    p, _, rendered = lab
    rendered["text"] = NS.format(name="default", labels="{}")
    with pytest.raises(LabError) as e:
        p.reset("demo")
    assert e.value.step == "render"


@pytest.mark.parametrize("source", ["../etc", "UPPER", "a" * 60, "missing"])
def test_unsafe_or_unknown_sources_rejected(lab, source):
    p, _, _ = lab
    with pytest.raises(LabError):
        p.source_dir(source)


# ---- step engine ------------------------------------------------------------
class Kube:
    """Records kubectl calls; `fail` maps a kubectl verb to an error message."""

    def __init__(self, rendered: str, workloads: str = "deployment.apps/api\n"):
        self.rendered, self.workloads, self.calls, self.fail, self.secrets = rendered, workloads, [], {}, set()

    def __call__(self, *args, step, stdin=None, **_):
        self.calls.append((args, stdin))
        if args[0] in self.fail:
            raise LabError(self.fail[args[0]], step)
        if args[0] == "kustomize":
            return self.rendered
        if args[:2] == ("get", "secret"):
            return f"secret/{args[2]}" if args[2] in self.secrets else ""
        if args[:2] == ("get", "deployments,statefulsets"):
            return self.workloads
        if args[0] == "delete":
            self.secrets.clear()  # deleting the namespace deletes its secrets
        if args[0] == "apply" and stdin and "kind: Secret" in stdin:
            self.secrets.add("db")
        return "ok\n"

    def verbs(self):
        return [a[0] for a, _ in self.calls]


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "kustomization.yaml").write_text("resources: []\n")
    (tmp_path / "demo" / "lab.yaml").write_text("url: http://localhost:8080\n"
                                                 "generated_secrets: [{name: db, keys: [password]}]\n")
    p = NamespaceLabProvisioner(tmp_path)
    kube = Kube(NS.format(name="lab-demo", labels=RESETTABLE))
    monkeypatch.setattr(p, "_kubectl", kube)
    return p, kube


def test_deploy_runs_named_steps_in_order(engine):
    p, kube = engine
    seen = []
    steps = p.run("deploy", "demo", lambda s: seen.append([x.state for x in s]))
    assert [s.name for s in steps] == ["render manifests", "create namespaces", "generate secrets",
                                       "apply manifests", "wait until ready"]
    assert all(s.state == "ok" and s.seconds is not None for s in steps)
    assert steps[0].detail == "namespaces: lab-demo" and steps[-1].detail == "1 workloads ready"
    assert seen[0][0] == "running" and seen[-1] == ["ok"] * 5


def test_generated_secret_is_random_sent_on_stdin_and_kept_on_redeploy(engine):
    p, kube = engine
    p.run("deploy", "demo")
    applied = [stdin for args, stdin in kube.calls if args[0] == "apply" and stdin and "kind: Secret" in stdin]
    assert len(applied) == 1 and "password:" in applied[0]
    assert all("password" not in " ".join(args) for args, _ in kube.calls)  # never on the command line
    kube.calls.clear()
    steps = p.run("deploy", "demo")  # re-applying keeps the existing credentials
    assert next(s for s in steps if s.name == "generate secrets").detail == "already present"
    steps = p.run("reset", "demo")  # reset deletes the namespace, so fresh credentials are made
    assert next(s for s in steps if s.name == "generate secrets").detail == "created db"


def test_failure_stops_at_the_failing_step_with_the_real_error(engine):
    p, kube = engine
    kube.fail["rollout"] = 'deployment "api" exceeded its progress deadline'
    with pytest.raises(LabError) as e:
        p.run("reset", "demo")
    assert e.value.step == "wait until ready"
    assert "exceeded its progress deadline" in str(e.value)
    assert "deployment.apps/api isn't ready" in str(e.value)


def test_failed_step_is_marked_and_later_steps_stay_pending(engine):
    p, kube = engine
    kube.fail["delete"] = "namespaces \"lab-demo\" is forbidden"
    last = {}
    with pytest.raises(LabError):
        p.run("reset", "demo", lambda s: last.update(steps=[(x.name, x.state) for x in s]))
    assert last["steps"][:3] == [("render manifests", "ok"), ("delete namespaces", "failed"),
                                 ("create namespaces", "pending")]


def test_reset_twice_is_the_same_plan(engine):
    p, kube = engine
    p.run("reset", "demo")
    first = kube.verbs()
    kube.calls.clear()
    p.run("reset", "demo")
    assert kube.verbs() == first and "delete" in first


def test_stop_scales_to_zero_and_never_deletes(engine):
    p, kube = engine
    p.run("stop", "demo")
    assert "delete" not in kube.verbs()
    scale = ("scale", "deployments,statefulsets", "--all", "--replicas=0", "-n", "lab-demo")
    assert scale in [a for a, _ in kube.calls]


def test_unknown_action_rejected(engine):
    p, _ = engine
    with pytest.raises(LabError):
        p.plan("format-disk", "demo")


def test_kubectl_errors_are_reported_verbatim(tmp_path):
    class Res:
        returncode, stdout, stderr = 1, "", "error: the server doesn't have a resource type \"x\"\n"

    p = NamespaceLabProvisioner(tmp_path, runner=lambda *a, **k: Res())
    with pytest.raises(LabError) as e:
        p._kubectl("get", "x", step="list")
    assert str(e.value) == 'error: the server doesn\'t have a resource type "x"' and e.value.step == "list"


def test_cloudmart_lab_is_well_formed():
    """The shipped lab: one resettable namespace, guardrails, no plaintext secrets."""
    import yaml

    from app.core.config import REPO_ROOT
    d = REPO_ROOT / "labs" / "cloudmart"
    docs = [x for f in d.glob("*.yaml") if f.name not in {"kustomization.yaml", "lab.yaml"}
            for x in yaml.safe_load_all(f.read_text()) if x]
    kinds = {x["kind"] for x in docs}
    assert {"Namespace", "ResourceQuota", "LimitRange", "NetworkPolicy", "Ingress"} <= kinds
    assert "Secret" not in kinds
    p = NamespaceLabProvisioner(REPO_ROOT / "labs")
    assert p.namespaces("cloudmart", docs) == ["lab-cloudmart"]
    for x in docs:
        pod = x.get("spec", {}).get("template", {}).get("spec")
        if pod:  # Docker-style service links inject e.g. REDIS_PORT=tcp://..., which broke the API
            assert pod.get("enableServiceLinks") is False, x["metadata"]["name"]
        for c in (x.get("spec", {}).get("template", {}).get("spec", {}).get("containers") or []):
            assert c.get("resources", {}).get("limits"), f"{x['metadata']['name']} has no limits"
            assert ":latest" not in c["image"] and ":" in c["image"]
