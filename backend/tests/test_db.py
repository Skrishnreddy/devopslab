from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.db.models import Base
from app.db.session import engine, migrate


def test_migrations_match_models():
    migrate()
    with engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models changed without a migration: {diff}"


def test_migrate_is_idempotent():
    migrate()
    migrate()
