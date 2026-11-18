import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.v1 import auth, cluster, engineer, learn, system, terminal
from .auth.provider import auth_provider
from .content.loader import get_content
from .core import errors
from .core.config import settings
from .db.session import get_db, migrate
from .providers import registry

log = logging.getLogger("devopslab")


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate()
    content = get_content()  # raises ContentError on invalid content: fail fast
    log.info("Content: %d tracks, %d projects, %d challenges",
             len(content.tracks), len(content.projects), len(content.challenges))
    db = next(get_db())
    try:
        token = auth_provider.ensure_admin(db)
    finally:
        db.close()
    origin = settings.allowed_origins[0]
    log.warning("DevOpsLab is ready. Log in at: %s/login#token=%s", origin, token)
    terminals = registry.terminal()
    terminals.on_close = terminal.record_close
    reaper = asyncio.create_task(_reap_terminals(terminals))
    yield
    reaper.cancel()
    await terminals.close_all()


async def _reap_terminals(mgr) -> None:
    """Delete pods left by a previous run, then enforce idle/max-length limits forever."""
    try:
        n = await mgr.reap_orphans()
        if n:
            log.info("Removed %d terminal pod(s) left from a previous run", n)
    except Exception as e:  # cluster down is normal; the Terminal page reports it
        log.info("Skipped terminal orphan cleanup (cluster unreachable: %s)", e.__class__.__name__)
    while True:
        await asyncio.sleep(settings.terminal_reap_interval_seconds)
        try:
            await mgr.reap()
        except Exception as e:
            log.warning("Terminal reaper failed: %s", e)


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = FastAPI(title="DevOpsLab API", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
    errors.install(app)
    for r in (system.public, auth.router, system.router, cluster.router, learn.router, engineer.router,
              terminal.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
