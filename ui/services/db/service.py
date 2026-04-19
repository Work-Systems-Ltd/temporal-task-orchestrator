"""DbService — composed from focused mixins."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .mixins import GroupsMixin, SessionsMixin, UsersMixin


class DbService(UsersMixin, GroupsMixin, SessionsMixin):
    """Unified service for all database interactions.

    Implementation is split across mixins:
      - UsersMixin:    user CRUD, assignment queries, seeding
      - GroupsMixin:   group CRUD, default group creation
      - SessionsMixin: session CRUD, expiry cleanup
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    @asynccontextmanager
    async def _session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._factory() as db:
            yield db
