from __future__ import annotations

from fastapi import HTTPException, Request, WebSocket, WebSocketException, status

from .models import User
from .session import load_user_from_session


class LoginRequiredError(HTTPException):
    """Raised when an unauthenticated user hits a protected route."""

    def __init__(self, redirect_to: str) -> None:
        super().__init__(status_code=303, detail="Login required")
        self.redirect_to = redirect_to


async def get_current_user(request: Request) -> User | None:
    secret = request.app.state.settings.session_secret
    return await load_user_from_session(request, secret)


async def require_auth(request: Request) -> User:
    user = await get_current_user(request)
    if user is None:
        raise LoginRequiredError(f"/login?next={request.url.path}")
    return user


async def require_admin(request: Request) -> User:
    user = await require_auth(request)
    if not any(g.name == "admin" for g in user.groups):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_ws_auth(ws: WebSocket) -> User:
    secret = ws.app.state.settings.session_secret
    user = await load_user_from_session(ws, secret)
    if user is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return user
