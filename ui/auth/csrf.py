"""Double-submit cookie CSRF protection.

How it works:
1. A random token is set as an httponly cookie (``_csrf``).
2. Every HTML form includes the same token in a hidden ``csrf_token`` field.
3. On POST, the middleware compares cookie vs. form field — mismatch → 403.

The token is generated once per session (on first GET) and rotated on login.
"""
from __future__ import annotations

import hmac
import secrets

from starlette.requests import Request
from starlette.responses import Response

COOKIE_NAME = "_csrf"
FORM_FIELD = "csrf_token"


def _make_token() -> str:
    return secrets.token_urlsafe(32)


def get_csrf_token(request: Request) -> str:
    """Return the current CSRF token, creating one if absent."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        token = _make_token()
        # Stash on request.state so the middleware can set the cookie
        request.state._csrf_new_token = token
    return token


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        path="/",
    )


async def validate_csrf(request: Request) -> bool:
    """Return True if the CSRF token is valid for this request.

    Caches the raw body so downstream handlers (FastAPI form parsing)
    can still read it.
    """
    cookie_token = request.cookies.get(COOKIE_NAME)
    if not cookie_token:
        return False

    # Cache the body so it can be re-read by FastAPI
    body = await request.body()
    request._body = body  # noqa: SLF001 — Starlette uses this cache

    form = await request.form()
    form_token = form.get(FORM_FIELD)
    if not form_token or not isinstance(form_token, str):
        return False

    return hmac.compare_digest(cookie_token, form_token)
