import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.v1 import auth, cluster, engineer, learn, system
from .auth.provider import auth_provider
from .content.loader import get_content
from .core import errors
from .core.config import settings
from .db.session import get_db, migrate

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
    yield


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = FastAPI(title="DevOpsLab API", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
    errors.install(app)
    for r in (system.public, auth.router, system.router, cluster.router, learn.router, engineer.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
