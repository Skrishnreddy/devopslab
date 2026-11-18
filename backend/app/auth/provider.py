"""Authentication providers.

Phase 1 ships LocalTokenAuth: a single local admin who logs in with a random
token stored (0600) in the data dir, like Jupyter. Password and OIDC providers
can implement the same interface for multi-user deployments.
"""
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from ..core.config import settings
from ..core.security import new_secret, sha256
from ..db.models import LoginToken, Session, User

log = logging.getLogger("devopslab.auth")


class AuthProvider(Protocol):
    def authenticate(self, db: DB, credential: str) -> User | None: ...


class LocalTokenAuth:
    ADMIN = "admin"

    def ensure_admin(self, db: DB) -> str:
        """Create the admin and a login token on first run. Returns the token."""
        user = db.scalar(select(User).where(User.username == self.ADMIN))
        if user is None:
            user = User(username=self.ADMIN, role="admin")
            db.add(user)
            db.flush()
        token_file = settings.token_file
        token = token_file.read_text().strip() if token_file.exists() else None
        active = db.scalar(
            select(LoginToken).where(LoginToken.user_id == user.id, LoginToken.revoked_at.is_(None))
        )
        if token is None or active is None or active.token_hash != sha256(token):
            token = self.rotate(db, user)
        db.commit()
        return token

    def rotate(self, db: DB, user: User) -> str:
        now = datetime.now(UTC)
        for t in db.scalars(select(LoginToken).where(LoginToken.user_id == user.id)):
            t.revoked_at = t.revoked_at or now
        token = new_secret()
        db.add(LoginToken(user_id=user.id, token_hash=sha256(token)))
        settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(settings.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(token + "\n")
        log.info("New login token written to %s", settings.token_file)
        return token

    def authenticate(self, db: DB, credential: str) -> User | None:
        row = db.scalar(
            select(LoginToken).where(LoginToken.token_hash == sha256(credential), LoginToken.revoked_at.is_(None))
        )
        return db.get(User, row.user_id) if row else None


def create_session(db: DB, user: User, user_agent: str | None) -> tuple[str, Session]:
    raw = new_secret()
    s = Session(
        id_hash=sha256(raw),
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.session_hours),
        user_agent=(user_agent or "")[:256],
    )
    db.add(s)
    db.commit()
    return raw, s


auth_provider = LocalTokenAuth()
