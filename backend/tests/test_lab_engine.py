import pytest

from app.config import settings
from app.services import lab_engine

NS = """apiVersion: v1
kind: Namespace
metadata:
  name: {name}
  labels: {labels}
"""


@pytest.fixture()
def lab(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "labs_dir", str(tmp_path))
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "kustomization.yaml").write_text("resources: []\n")
    calls = []
    rendered = {"text": ""}

    def fake(*args, input_text=None):
        calls.append(args)
        return rendered["text"] if args[0] == "kustomize" else "namespace/x configured\n"

    monkeypatch.setattr(lab_engine, "_kubectl", fake)
    return calls, rendered


def test_reset_only_deletes_resettable_namespaces(lab):
    calls, rendered = lab
    rendered["text"] = (
        NS.format(name="lab-demo", labels='{"devopslab.io/resettable": "true"}')
        + "---\n"
        + NS.format(name="kube-system", labels="{}")
    )
    out = lab_engine.reset("demo")
    assert out["reset_namespaces"] == ["lab-demo"]
    deleted = [c[2] for c in calls if c[0] == "delete"]
    assert deleted == ["lab-demo"]


def test_reset_refuses_when_nothing_is_resettable(lab):
    _, rendered = lab
    rendered["text"] = NS.format(name="default", labels="{}")
    with pytest.raises(lab_engine.LabError):
        lab_engine.reset("demo")
