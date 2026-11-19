"""Read-only views of the lab cluster. Errors from the API server are passed on verbatim."""
import asyncio
import contextlib
import json
import time
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from ...auth.deps import current_principal
from ...core.errors import AppError
from ...providers import registry
from ...providers.cluster import ClusterAPIError, ClusterUnavailable

router = APIRouter(prefix="/cluster", tags=["cluster"], dependencies=[Depends(current_principal)])

DNS = r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$"
NAME = r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$"
Namespace = Annotated[str | None, Query(pattern=DNS)]
NsPath = Annotated[str, Path(pattern=DNS)]
NamePath = Annotated[str, Path(pattern=NAME)]
FOLLOW_MAX_SECONDS = 30 * 60


async def stop_stream(resp, reader: asyncio.Future) -> None:
    """End a follow stream without blocking the event loop.

    The reader thread holds the response's buffer lock while it waits in
    recv(), so close() on the event loop would wait forever (found on the Mac:
    the whole API froze when a browser left the logs view). shutdown() closes
    the socket underneath the reader, which wakes it; only then is the
    connection released, off the loop.
    """
    with contextlib.suppress(Exception):
        resp.shutdown()
    with contextlib.suppress(Exception):
        await asyncio.wait_for(asyncio.shield(reader), timeout=5)

    def _release():
        with contextlib.suppress(Exception):
            resp.release_conn()

    await asyncio.to_thread(_release)


def _call(fn: Callable[..., Any], *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ClusterUnavailable as e:
        raise AppError(503, "cluster_unreachable", str(e)) from e
    except ClusterAPIError as e:
        status = e.status if e.status in {400, 403, 404, 409} else 502
        raise AppError(status, "kubernetes_error", e.message, {"status": e.status}) from e


@router.get("/summary")
def summary():
    return registry.cluster().summary()


@router.get("/namespaces")
def namespaces():
    return _call(registry.cluster().namespaces)


@router.get("/pods")
def pods(namespace: Namespace = None):
    return _call(registry.cluster().pods, namespace)


@router.get("/deployments")
def deployments(namespace: Namespace = None):
    return _call(registry.cluster().deployments, namespace)


@router.get("/services")
def services(namespace: Namespace = None):
    return _call(registry.cluster().services, namespace)


@router.get("/events")
def events(namespace: Namespace = None, limit: int = Query(200, ge=1, le=1000)):
    return _call(registry.cluster().events, namespace, limit)


@router.get("/pods/{namespace}/{name}")
def pod(namespace: NsPath, name: NamePath):
    return _call(registry.cluster().pod, namespace, name)


@router.get("/yaml/{kind}/{name}", response_class=PlainTextResponse)
def yaml_cluster_scoped(kind: str, name: NamePath):
    return _call(registry.cluster().yaml, kind, None, name)


@router.get("/yaml/{kind}/{namespace}/{name}", response_class=PlainTextResponse)
def yaml_namespaced(kind: str, namespace: NsPath, name: NamePath):
    return _call(registry.cluster().yaml, kind, namespace, name)


@router.get("/pods/{namespace}/{name}/logs")
async def logs(request: Request, namespace: NsPath, name: NamePath,
               container: Annotated[str | None, Query(pattern=DNS)] = None,
               tail: int = Query(200, ge=1, le=5000), previous: bool = False, follow: bool = False):
    cluster = registry.cluster()
    if not follow:
        text = await asyncio.to_thread(_call, cluster.logs, namespace, name, container, tail, previous)
        return PlainTextResponse(text)

    resp = await asyncio.to_thread(_call, cluster.follow_logs, namespace, name, container, tail)

    async def events():
        """Server-sent events: {"line": ...} per log line, then {"end": reason}."""
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def pump():
            buf = b""
            try:
                for chunk in resp.stream(4096, decode_content=True):
                    buf += chunk
                    *lines, buf = buf.split(b"\n")
                    for line in lines:
                        loop.call_soon_threadsafe(queue.put_nowait, line.decode(errors="replace"))
                if buf:
                    loop.call_soon_threadsafe(queue.put_nowait, buf.decode(errors="replace"))
            except Exception:  # noqa: S110 - connection closed by us or the API server
                pass
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        reader = asyncio.ensure_future(asyncio.to_thread(pump))
        started = time.monotonic()
        reason = "The log stream ended (the container stopped or was restarted)."
        try:
            while True:
                if await request.is_disconnected():
                    return
                if time.monotonic() - started > FOLLOW_MAX_SECONDS:
                    reason = "Live logs stop after 30 minutes. Follow again to continue."
                    break
                try:
                    line = await asyncio.wait_for(queue.get(), timeout=5)  # also how fast a disconnect is noticed
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if line is None:
                    break
                yield f"data: {json.dumps({'line': line})}\n\n"
            yield f"data: {json.dumps({'end': reason})}\n\n"
        finally:
            await asyncio.shield(stop_stream(resp, reader))  # runs to the end even if we're cancelled

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
