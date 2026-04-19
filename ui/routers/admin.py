from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from ui.auth.database import get_session_factory
from ui.auth.dependencies import require_admin
from ui.auth.models import Group, User
from ui.dependencies import get_templates

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_class=HTMLResponse)
async def user_list(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(User).order_by(User.username))
        users = result.scalars().all()
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "users": users},
    )


@router.get("/groups", response_class=HTMLResponse)
async def group_list(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(Group).order_by(Group.name))
        groups = result.scalars().all()
    return templates.TemplateResponse(
        "admin_groups.html",
        {"request": request, "groups": groups},
    )
