from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.hash import bcrypt
from sqlalchemy import select

from ui.dependencies import get_templates

from .database import get_session_factory
from .dependencies import get_current_user
from .models import User
from .session import create_session, delete_session

router = APIRouter(tags=["auth"])


def _safe_next_url(url: str) -> str:
    """Return *url* only if it's a safe, relative path; otherwise fall back to '/'."""
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return "/"
    if not url.startswith("/"):
        return "/"
    return url


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
    user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": None,
            "next_url": _safe_next_url(request.query_params.get("next", "/")),
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/"),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse | RedirectResponse:
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(User).where(User.username == username, User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()

    if not user or not bcrypt.verify(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid username or password",
                "next_url": next_url,
            },
        )

    response = RedirectResponse(url=_safe_next_url(next_url), status_code=303)
    secret = request.app.state.settings.session_secret
    await create_session(user, response, secret)
    return response


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    secret = request.app.state.settings.session_secret
    await delete_session(request, response, secret)
    return response
