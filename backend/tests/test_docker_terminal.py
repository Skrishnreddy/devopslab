"""Docker terminal (Phase 2b): container spec, VM lifecycle and isolation files."""
import asyncio
import subprocess
from pathlib import Path

import pytest

from app.core.config import settings
from app.providers import docker_terminal as dt
from app.providers.terminal import TerminalError, TerminalManager
from tests.terminal_fakes import FakeBackend

REPO = Path(__file__).resolve().parents[2]
SID = "t-0123456789abcdef0123456789abcdef"


def test_container_has_no_host_access_and_is_limited():
    spec = dt.build_container(SID, 7)
    hc = spec["host_config"]
    assert spec["image"] == dt.DOCKER_IMAGE
    assert hc["binds"] == []  # no host folders, no Docker socket
    assert "volumes" not in spec and "devices" not in hc
    assert hc["mem_limit"] == "1g" and hc["memswap_limit"] == "1g"
    assert hc["nano_cpus"] == 1_000_000_000 and hc["pids_limit"] == 1024
    assert hc["network_mode"] == spec["network"] == dt.network_name(SID)  # own network per session
    assert hc.get("pid_mode") is None and hc.get("ipc_mode") is None
    assert spec["labels"]["devopslab.io/owner"] == "7"
    assert spec["labels"]["devopslab.io/terminal-session"] == SID


def test_image_and_script_agree():
    script = (REPO / "infra/scripts/docker-vm.sh").read_text()
    assert f'IMAGE="{dt.DOCKER_IMAGE}"' in script
    env = (REPO / "infra/config.env").read_text()
    assert f"DOCKER_VM_PROFILE={settings.docker_vm_profile}" in env


def test_docker_image_runs_learner_as_non_root():
    df = (REPO / "images/docker-terminal/Dockerfile").read_text()
    assert "FROM docker:27.5.1-dind-rootless" in df
    assert "\nUSER rootless\n" in df


def test_vm_never_mounts_your_home_folder():
    script = (REPO / "infra/scripts/docker-vm.sh").read_text()
    assert '--mount "$SHARE"' in script  # only an empty folder; replaces Colima's default home mount
    assert 'test -e "$HOME/Library"' in script  # and refuses to run if home leaked anyway


def test_firewall_blocks_gateway_and_link_local():
    fw = (REPO / "infra/docker-vm/firewall.sh").read_text()
    assert '-d "$NET" -j REJECT' in fw  # Lima gateway network forwards to your Mac's localhost
    assert "-d 169.254.0.0/16 -j REJECT" in fw
    assert "DOCKER-USER -j DEVOPSLAB-SANDBOX" in fw
    assert "-A DEVOPSLAB-SANDBOX-IN -j REJECT" in fw  # containers can't open connections to the VM


class Runner:
    def __init__(self, code=0, out="", err=""):
        self.calls, self.code, self.out, self.err = [], code, out, err

    def __call__(self, argv, **kw):
        self.calls.append(argv[1])
        return subprocess.CompletedProcess(argv, self.code, self.out, self.err)


def test_vm_start_failure_is_reported_with_the_reason():
    b = dt.DockerVMBackend(runner=Runner(1, "", "==> Starting\nxx colima: not enough memory"))
    with pytest.raises(TerminalError) as e:
        b.create(SID, 1, "docker")
    assert e.value.code == "docker_vm_failed"
    assert "not enough memory" in e.value.message and "make docker-vm-up" in e.value.message


def test_vm_stops_after_idle_and_not_before(monkeypatch):
    t = [1000.0]
    runner = Runner()
    b = dt.DockerVMBackend(clock=lambda: t[0], runner=runner)
    monkeypatch.setattr(b, "vm_running", lambda: True)
    b.on_reap(1)
    t[0] += settings.docker_vm_idle_seconds + 100
    b.on_reap(1)  # still in use
    assert runner.calls == []
    t[0] += settings.docker_vm_idle_seconds - 1
    b.on_reap(0)
    assert runner.calls == []
    t[0] += 2
    b.on_reap(0)
    assert runner.calls == ["down"]
    b.on_reap(0)  # doesn't keep calling
    assert runner.calls == ["down"]


def test_vm_not_running_means_no_sessions_and_nothing_to_delete(monkeypatch, tmp_path):
    b = dt.DockerVMBackend(runner=Runner())
    monkeypatch.setattr(b, "vm_running", lambda: False)
    assert b.list_sessions() == []
    b.delete("term-x")  # no error


def test_manager_routes_docker_sessions_to_the_vm_backend():
    pods, vm = FakeBackend(), FakeBackend()
    mgr = TerminalManager({"linux": pods, "kubernetes": pods, "docker": vm})

    async def run():
        d = await mgr.open(1, "docker")
        k = await mgr.open(1, "kubernetes")
        await mgr.reap()
        return d, k

    d, k = asyncio.run(run())
    assert list(vm.pods) == [d.pod] and list(pods.pods) == [k.pod]
    assert vm.reaps == [1] and pods.reaps == [1]
