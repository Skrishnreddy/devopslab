"""In-memory stand-ins for the Kubernetes pod backend."""
import asyncio

from app.providers.terminal import TerminalError


class FakeStream:
    def __init__(self, loop):
        self.written: list[bytes] = []
        self.resizes: list[tuple[int, int]] = []
        self.closed = False
        self._q: asyncio.Queue = asyncio.Queue()
        self._loop = loop

    def feed(self, data: bytes | None) -> None:
        self._loop.call_soon_threadsafe(self._q.put_nowait, data)

    def write(self, data: bytes) -> None:
        self.written.append(data)
        self.feed(b"echo:" + data)

    def resize(self, cols: int, rows: int) -> None:
        self.resizes.append((cols, rows))

    async def output(self):
        while (chunk := await self._q.get()) is not None:
            yield chunk

    def close(self) -> None:
        self.closed = True


class FakeBackend:
    def __init__(self, fail_ready: TerminalError | None = None):
        self.pods: dict[str, dict] = {}
        self.deleted: list[str] = []
        self.fail_ready = fail_ready
        self.streams: list[FakeStream] = []
        self.extra_sessions: list[str] = []

    def create(self, manifest: dict) -> None:
        self.pods[manifest["metadata"]["name"]] = manifest

    def wait_ready(self, name: str, timeout: float) -> None:
        if self.fail_ready:
            raise self.fail_ready

    def delete(self, name: str) -> None:
        self.deleted.append(name)
        self.pods.pop(name, None)

    def list_sessions(self) -> list[str]:
        return [m["metadata"]["labels"]["devopslab.io/terminal-session"] for m in self.pods.values()] \
            + self.extra_sessions

    def exec_shell(self, name: str, loop) -> FakeStream:
        assert name in self.pods
        s = FakeStream(loop)
        self.streams.append(s)
        return s
