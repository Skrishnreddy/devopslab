from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        url = settings.resolved_database_url
        if url.startswith("sqlite"):
            settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        _engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk_on(conn, _):  # SQLite ignores foreign keys unless asked
                conn.execute("PRAGMA foreign_keys=ON")
        _factory = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Used by tests after changing settings.database_url."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = _factory = None


def get_db() -> Iterator[Session]:
    engine()
    if _factory is None:  # pragma: no cover
        raise RuntimeError("database not initialised")
    with _factory() as db:
        yield db


def migrate() -> None:
    """Bring the schema to head with Alembic."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    here = Path(__file__).resolve().parents[2]
    cfg = Config(str(here / "alembic.ini"))
    cfg.set_main_option("script_location", str(here / "alembic"))
    cfg.attributes["engine"] = engine()
    command.upgrade(cfg, "head")
