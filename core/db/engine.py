from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    global _engine, _session_factory
    _engine = create_async_engine(database_url, pool_size=5, max_overflow=10)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    if _engine:
        await _engine.dispose()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    assert _session_factory is not None, "Database not initialized — call init_engine first"
    return _session_factory
