"""SQLite progress store. Small on purpose: one table per concept, no ORM."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS module_progress (
    module_id    TEXT PRIMARY KEY,
    track_id     TEXT NOT NULL,
    completed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS challenge_attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    hints_used   INTEGER NOT NULL DEFAULT 0,
    result       TEXT
);
"""


@contextmanager
def connect(path: str | None = None):
    conn = sqlite3.connect(path or settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: str | None = None) -> None:
    with connect(path) as c:
        c.executescript(SCHEMA)


def completed_modules() -> dict[str, str]:
    with connect() as c:
        rows = c.execute("SELECT module_id, track_id FROM module_progress").fetchall()
    return {r["module_id"]: r["track_id"] for r in rows}


def set_module_complete(module_id: str, track_id: str, done: bool) -> None:
    with connect() as c:
        if done:
            c.execute(
                "INSERT OR REPLACE INTO module_progress VALUES (?, ?, ?)",
                (module_id, track_id, datetime.now(timezone.utc).isoformat()),
            )
        else:
            c.execute("DELETE FROM module_progress WHERE module_id = ?", (module_id,))
