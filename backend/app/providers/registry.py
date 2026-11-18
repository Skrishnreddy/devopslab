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
    kind = cluster()
    return TerminalManager(KubePodBackend(api_factory=kind._api))  # type: ignore[attr-defined]
