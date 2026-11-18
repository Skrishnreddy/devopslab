"""Selects provider implementations. Swap here for other platforms."""
from functools import cache

from .ai import AIProvider, OllamaProvider
from .cluster import ClusterProvider, KindCluster
from .runtime import ColimaRuntime, ContainerRuntime
from .terminal import KubePodBackend, TerminalManager


@cache
def runtime() -> ContainerRuntime:
    return ColimaRuntime()


@cache
def cluster() -> ClusterProvider:
    return KindCluster()


@cache
def ai() -> AIProvider:
    return OllamaProvider()


@cache
def terminal() -> TerminalManager:
    from .docker_terminal import DockerVMBackend

    pods = KubePodBackend(api_factory=cluster()._api)  # type: ignore[attr-defined]
    return TerminalManager({"linux": pods, "kubernetes": pods, "docker": DockerVMBackend()})


@cache
def lab_ops():
    from .lab_ops import LabOperations

    return LabOperations()
