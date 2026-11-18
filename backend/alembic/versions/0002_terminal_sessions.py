"""terminal session audit table

Revision ID: 0002
Revises: 0001
"""
from collections.abc import Sequence

import sqlalchemy as sa

import app.db.models
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "terminal_sessions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("profile", sa.String(length=16), nullable=False),
        sa.Column("pod", sa.String(length=64), nullable=False),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("closed_at", app.db.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_terminal_sessions_user_id"), "terminal_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_terminal_sessions_user_id"), table_name="terminal_sessions")
    op.drop_table("terminal_sessions")
