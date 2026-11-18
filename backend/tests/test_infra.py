import json
import urllib.error

import pytest

from app.providers import ai as ai_mod
from app.providers import cluster as cluster_mod
from app.providers import commands, runtime
from app.providers.commands import Result


def fake_runner(table: dict[tuple, Result]):
    async def _run(*argv, timeout=None):
        for prefix, result in table.items():
            if argv[: len(prefix)] == prefix:
                return result
        return Result(False, "", f"{argv[0]} not found on PATH", None, missing=True)
    return _run


def ok(out=""):
    return Result(True, out, "", 0)


def patch_run(monkeypatch, table):
    fn = fake_runner(table)
    for mod in (runtime, cluster_mod):
        monkeypatch.setattr(mod, "run", fn)
    monkeypatch.setattr(ai_mod, "_get_json", ollama_down)


def ollama_down(url, timeout):
    raise urllib.error.URLError("Connection refused")


@pytest.mark.anyio
async def test_real_run_reports_missing_binary():
    r = await commands.run("definitely-not-a-real-binary-xyz")
    assert r.missing and not r.ok


def test_all_missing_is_reported_honestly(authed, monkeypatch):
    patch_run(monkeypatch, {})
    body = authed.get("/api/v1/infra/health").json()
    by_id = {c["id"]: c for c in body["components"]}
    assert set(by_id) == {"colima", "docker", "kind", "kubectl", "helm", "kubernetes", "ollama"}
    assert by_id["colima"]["status"] == "missing"
    assert by_id["kubernetes"]["status"] == "warning"  # no kubeconfig
    assert body["overall"] == "missing"


def test_installed_but_stopped(authed, monkeypatch):
    patch_run(monkeypatch, {
        ("colima", "version"): ok("colima version 0.8.1\ngit commit: abc"),
        ("colima", "status"): Result(False, "", "colima [profile=devopslab] is not running", 1),
        ("docker",): Result(False, "", "Cannot connect to the Docker daemon", 1),
        ("kind", "get"): Result(False, "", "failed to list nodes", 1),
        ("kind", "version"): ok("kind v0.26.0 go1.23.4 darwin/arm64"),
        ("kubectl",): ok(json.dumps({"clientVersion": {"gitVersion": "v1.31.4"}})),
        ("helm",): ok("v3.16.4+g7877b45"),
    })
    by_id = {c["id"]: c for c in authed.get("/api/v1/infra/health").json()["components"]}
    assert by_id["colima"] == {**by_id["colima"], "status": "warning", "version": "0.8.1",
                               "remediation": "Run `make up`"}
    assert by_id["docker"]["status"] == "warning"
    assert by_id["kind"]["status"] == "warning" and by_id["kind"]["version"] == "0.26.0"
    assert by_id["kubectl"]["version"] == "1.31.4"
    assert by_id["helm"]["version"] == "3.16.4"


def test_running_runtime(authed, monkeypatch):
    info = {"ServerVersion": "27.4.0", "NCPU": 4, "MemTotal": 6 * 2**30, "Architecture": "aarch64",
            "ContainersRunning": 3}
    patch_run(monkeypatch, {
        ("colima", "version"): ok("colima version 0.8.1"),
        ("colima", "status"): ok(),
        ("docker",): ok(json.dumps(info)),
        ("kind", "get"): ok("cloudmart\nother"),
        ("kind", "version"): ok("kind v0.26.0 go1.23.4 darwin/arm64"),
    })
    by_id = {c["id"]: c for c in authed.get("/api/v1/infra/health").json()["components"]}
    assert by_id["colima"]["status"] == "ok"
    assert by_id["docker"]["status"] == "ok" and by_id["docker"]["message"] == "4 CPU, 6.0 GiB, aarch64"
    assert by_id["kind"]["status"] == "ok"


def test_ollama_down_is_optional_and_does_not_affect_overall(authed, monkeypatch):
    info = {"ServerVersion": "27.4.0", "NCPU": 4, "MemTotal": 6 * 2**30, "Architecture": "aarch64"}
    patch_run(monkeypatch, {
        ("colima", "version"): ok("colima version 0.8.1"), ("colima", "status"): ok(),
        ("docker",): ok(json.dumps(info)), ("kind", "get"): ok("cloudmart"), ("kind", "version"): ok("kind v0.26.0"),
        ("kubectl",): ok(json.dumps({"clientVersion": {"gitVersion": "v1.31.4"}})), ("helm",): ok("v3.16.4"),
    })
    monkeypatch.setattr(cluster_mod.KindCluster, "_api_health",
                        lambda self: cluster_mod.ComponentHealth(id="kubernetes", name="Kubernetes API",
                                                                 status="ok", message="ok"))
    body = authed.get("/api/v1/infra/health").json()
    ollama = next(c for c in body["components"] if c["id"] == "ollama")
    assert ollama["status"] == "warning" and ollama["optional"] is True
    assert "ollama serve" in ollama["remediation"]
    assert body["overall"] == "ok"


def test_ollama_running_reports_version_and_models(authed, monkeypatch):
    patch_run(monkeypatch, {})

    def fake(url, timeout):
        assert url.startswith("http://127.0.0.1:11434/")
        return {"version": "0.5.4"} if url.endswith("/api/version") else {"models": [{"name": "qwen2.5-coder:7b"}]}

    monkeypatch.setattr(ai_mod, "_get_json", fake)
    ollama = next(c for c in authed.get("/api/v1/infra/health").json()["components"] if c["id"] == "ollama")
    assert ollama["status"] == "ok" and ollama["version"] == "0.5.4" and ollama["message"] == "1 model installed"


@pytest.mark.parametrize("url", ["http://10.0.0.5:11434", "https://api.example.com"])
def test_ollama_url_must_be_local(url):
    from pydantic import ValidationError

    from app.core.config import Settings
    with pytest.raises(ValidationError, match="127.0.0.1"):
        Settings(ollama_url=url)
