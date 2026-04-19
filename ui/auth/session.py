from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from starlette.requests import HTTPConnection
from starlette.responses import Response

from .database import get_session_factory
from .models import Session as SessionModel
from .models import User

COOKIE_NAME = "session_id"
SESSION_MAX_AGE = timedelta(days=7)


def _sign(session_id: str, secret: str) -> str:
    sig = hmac.new(secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()
    return f"{session_id}.{sig}"


def _verify(cookie_value: str, secret: str) -> str | None:
    if "." not in cookie_value:
        return None
    session_id, sig = cookie_value.rsplit(".", 1)
    expected = hmac.new(secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected):
        return session_id
    return None


async def create_session(user: User, response: Response, secret: str) -> None:
    factory = get_session_factory()
    async with factory() as db:
        session = SessionModel(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + SESSION_MAX_AGE,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    signed = _sign(str(session.id), secret)
    response.set_cookie(
        COOKIE_NAME,
        signed,
        max_age=int(SESSION_MAX_AGE.total_seconds()),
        httponly=True,
        samesite="lax",
        path="/",
    )


async def load_user_from_session(
    conn: HTTPConnection, secret: str
) -> User | None:
    cookie = conn.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    session_id = _verify(cookie, secret)
    if not session_id:
        return None
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        return None

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == sid,
                SessionModel.expires_at > datetime.now(timezone.utc),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
        return session.user


async def delete_expired_sessions() -> int:
    """Purge all expired sessions from the database. Returns count deleted."""
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            delete(SessionModel).where(
                SessionModel.expires_at <= datetime.now(timezone.utc)
            )
        )
        await db.commit()
        return result.rowcount  # type: ignore[return-value]


async def delete_session(
    conn: HTTPConnection, response: Response, secret: str
) -> None:
    cookie = conn.cookies.get(COOKIE_NAME)
    if cookie:
        session_id = _verify(cookie, secret)
        if session_id:
            try:
                sid = uuid.UUID(session_id)
            except ValueError:
                pass
            else:
                factory = get_session_factory()
                async with factory() as db:
                    await db.execute(
                        delete(SessionModel).where(SessionModel.id == sid)
                    )
                    await db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
