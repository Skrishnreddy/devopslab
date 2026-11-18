"""Terminal provider interface. Implementation arrives in Phase 2.

Contract (docs/security/terminal.md): sessions run in disposable sandbox pods
and are bridged over the Kubernetes exec API. Implementations must never start
a process on the host.
"""
from collections.abc import AsyncIterator
from typing import Literal, Protocol

Profile = Literal["linux", "kubernetes", "docker"]


class TerminalSession(Protocol):
    id: str
    profile: Profile

    async def write(self, data: bytes) -> None: ...
    async def resize(self, cols: int, rows: int) -> None: ...
    def output(self) -> AsyncIterator[bytes]: ...
    async def close(self) -> None: ...


class TerminalProvider(Protocol):
    async def open(self, user_id: int, profile: Profile, lab_id: str | None) -> TerminalSession: ...
    async def reap_orphans(self) -> int: ...
