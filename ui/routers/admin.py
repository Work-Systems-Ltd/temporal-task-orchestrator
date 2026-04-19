from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from ui.auth.database import get_session_factory
from ui.auth.dependencies import require_admin
from ui.auth.models import Group, User
from ui.dependencies import get_templates

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

ADMIN_TABS = ["users", "groups"]


# ---------------------------------------------------------------------------
# List views
# ---------------------------------------------------------------------------

@router.get("/users", response_class=HTMLResponse)
async def user_list(
    request: Request,
    q: str | None = Query(None),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    search = q.strip() if q else None
    factory = get_session_factory()
    async with factory() as db:
        stmt = select(User).order_by(User.username)
        if search:
            stmt = stmt.where(User.username.ilike(f"%{search}%"))
        result = await db.execute(stmt)
        users = result.scalars().all()
        result = await db.execute(select(Group).order_by(Group.name))
        groups = result.scalars().all()

        user_count = len(users) if search else (await db.execute(select(User))).scalars().all().__len__()
        group_count = (await db.execute(select(Group))).scalars().all().__len__()

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "users": users,
            "groups": groups,
            "search": search or "",
            "tab": "users",
            "tabs": ADMIN_TABS,
            "counts": {"users": user_count, "groups": group_count},
        },
    )


@router.get("/groups", response_class=HTMLResponse)
async def group_list(
    request: Request,
    q: str | None = Query(None),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    search = q.strip() if q else None
    factory = get_session_factory()
    async with factory() as db:
        stmt = select(Group).order_by(Group.name)
        if search:
            stmt = stmt.where(Group.name.ilike(f"%{search}%"))
        result = await db.execute(stmt)
        groups = result.scalars().all()

        user_count = (await db.execute(select(User))).scalars().all().__len__()
        group_count = len(groups) if search else (await db.execute(select(Group))).scalars().all().__len__()

    return templates.TemplateResponse(
        "admin_groups.html",
        {
            "request": request,
            "groups": groups,
            "search": search or "",
            "tab": "groups",
            "tabs": ADMIN_TABS,
            "counts": {"users": user_count, "groups": group_count},
        },
    )


# ---------------------------------------------------------------------------
# User actions
# ---------------------------------------------------------------------------

@router.post("/users/add")
async def user_add(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(""),
    password: str = Form(...),
    group_ids: list[str] = Form(default=[]),
) -> RedirectResponse:
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            return RedirectResponse(url="/admin/users?error=exists", status_code=303)

        groups: list[Group] = []
        for gid in group_ids:
            result = await db.execute(select(Group).where(Group.id == gid))
            group = result.scalar_one_or_none()
            if group:
                groups.append(group)

        user = User(
            username=username,
            display_name=display_name or username,
            password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            groups=groups,
        )
        db.add(user)
        await db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/reset-password")
async def user_reset_password(
    user_id: str,
    password: str = Form(...),
) -> RedirectResponse:
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            await db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/delete")
async def user_delete(
    request: Request,
    user_id: str,
) -> RedirectResponse:
    current_user = request.state.user
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and str(user.id) != str(current_user.id):
            await db.delete(user)
            await db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/groups")
async def user_update_groups(
    user_id: str,
    group_ids: list[str] = Form(default=[]),
) -> RedirectResponse:
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            groups: list[Group] = []
            for gid in group_ids:
                result = await db.execute(select(Group).where(Group.id == gid))
                group = result.scalar_one_or_none()
                if group:
                    groups.append(group)
            user.groups = groups
            await db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


# ---------------------------------------------------------------------------
# Group actions
# ---------------------------------------------------------------------------

@router.post("/groups/add")
async def group_add(
    request: Request,
    name: str = Form(...),
) -> RedirectResponse:
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(Group).where(Group.name == name))
        if result.scalar_one_or_none():
            return RedirectResponse(url="/admin/groups?error=exists", status_code=303)
        db.add(Group(name=name))
        await db.commit()
    return RedirectResponse(url="/admin/groups", status_code=303)


@router.post("/groups/{group_id}/delete")
async def group_delete(
    group_id: str,
) -> RedirectResponse:
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(Group).where(Group.id == group_id))
        group = result.scalar_one_or_none()
        if group:
            await db.delete(group)
            await db.commit()
    return RedirectResponse(url="/admin/groups", status_code=303)
