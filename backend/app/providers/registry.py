"""Selects provider implementations. Swap here for other platforms."""
from functools import cache

from .cluster import ClusterProvider, KindCluster
from .runtime import ColimaRuntime, ContainerRuntime


@cache
def runtime() -> ContainerRuntime:
    return ColimaRuntime()


@cache
def cluster() -> ClusterProvider:
    return KindCluster()
