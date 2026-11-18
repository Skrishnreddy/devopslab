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

    def fake(*args, step):
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
