"""Mixin for session CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from core.db.models import Session as SessionModel, User

SESSION_MAX_AGE = timedelta(days=7)


class SessionsMixin:
    """Session queries and mutations."""

    async def create_session(self, user_id: uuid.UUID) -> SessionModel:
        async with self._session() as db:
            session = SessionModel(
                user_id=user_id,
                expires_at=datetime.now(timezone.utc) + SESSION_MAX_AGE,
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session

    async def load_user_from_session_id(self, session_id: uuid.UUID) -> User | None:
        async with self._session() as db:
            result = await db.execute(
                select(SessionModel).where(
                    SessionModel.id == session_id,
                    SessionModel.expires_at > datetime.now(timezone.utc),
                )
            )
            session = result.scalar_one_or_none()
            return session.user if session else None

    async def delete_session_by_id(self, session_id: uuid.UUID) -> None:
        async with self._session() as db:
            await db.execute(delete(SessionModel).where(SessionModel.id == session_id))
            await db.commit()

    async def delete_expired_sessions(self) -> int:
        async with self._session() as db:
            result = await db.execute(
                delete(SessionModel).where(SessionModel.expires_at <= datetime.now(timezone.utc))
            )
            await db.commit()
            return result.rowcount  # type: ignore[return-value]
