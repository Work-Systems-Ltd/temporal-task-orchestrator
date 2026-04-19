import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from ui.auth.models import Base
from ui.config import AppSettings

target_metadata = Base.metadata


def _get_url() -> str:
    """Resolve database URL from alembic config (set by CLI) or settings."""
    url = context.config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return AppSettings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(_get_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
