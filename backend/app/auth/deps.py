from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Request
from sqlalchemy.orm import Session as DB

from ..core.config import settings
from ..core.errors import AppError
from ..core.security import sha256
from ..db.models import Session, User
from ..db.session import get_db

COOKIE = "devopslab_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass
class Principal:
    user: User
    session: Session


def check_origin(request: Request) -> None:
    """CSRF guard: writes must come from an allowed browser origin."""
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin not in settings.allowed_origins:
        raise AppError(403, "bad_origin", "Request origin is not allowed")


def current_principal(request: Request, db: DB = Depends(get_db)) -> Principal:
    raw = request.cookies.get(COOKIE)
    if not raw:
        raise AppError(401, "unauthorized", "Log in to continue")
    s = db.get(Session, sha256(raw))
    now = datetime.now(UTC)
    if s is None or s.expires_at <= now:
        raise AppError(401, "session_expired", "Your session has expired; log in again")
    check_origin(request)
    if now - s.last_seen_at > timedelta(minutes=1):
        s.last_seen_at = now
        db.commit()
    user = db.get(User, s.user_id)
    if user is None:
        raise AppError(401, "unauthorized", "Unknown user")
    return Principal(user=user, session=s)
