from alembic import context
from app.db.models import Base
from app.db.session import engine as app_engine

config = context.config
target_metadata = Base.metadata


def run() -> None:
    connectable = config.attributes.get("engine") or app_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


run()
