from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from ui.auth.database import get_session_factory
from ui.auth.dependencies import require_admin
from ui.auth.models import Group, User
from ui.dependencies import get_templates

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Single admin page — both tabs loaded, Alpine switches client-side
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    tab: str = Query("users"),
    q: str | None = Query(None),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    search = q.strip() if q else None
    factory = get_session_factory()
    async with factory() as db:
        # Users
        user_stmt = select(User).order_by(User.username)
        if search and tab == "users":
            user_stmt = user_stmt.where(User.username.ilike(f"%{search}%"))
        users = (await db.execute(user_stmt)).scalars().all()

        # Groups
        group_stmt = select(Group).order_by(Group.name)
        if search and tab == "groups":
            group_stmt = group_stmt.where(Group.name.ilike(f"%{search}%"))
        groups = (await db.execute(group_stmt)).scalars().all()

        # Counts (always unfiltered)
        user_count = (await db.execute(select(func.count(User.id)))).scalar()
        group_count = (await db.execute(select(func.count(Group.id)))).scalar()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "users": users,
            "groups": groups,
            "search": search or "",
            "tab": tab if tab in ("users", "groups") else "users",
            "counts": {"users": user_count, "groups": group_count},
        },
    )


# Keep old paths working as redirects
@router.get("/users", response_class=HTMLResponse)
async def users_redirect(q: str | None = Query(None)) -> RedirectResponse:
    url = "/admin?tab=users"
    if q:
        url += f"&q={q}"
    return RedirectResponse(url=url, status_code=303)


@router.get("/groups", response_class=HTMLResponse)
async def groups_redirect(q: str | None = Query(None)) -> RedirectResponse:
    url = "/admin?tab=groups"
    if q:
        url += f"&q={q}"
    return RedirectResponse(url=url, status_code=303)


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
            return RedirectResponse(url="/admin?tab=users&error=exists", status_code=303)

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
    return RedirectResponse(url="/admin?tab=users", status_code=303)


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
    return RedirectResponse(url="/admin?tab=users", status_code=303)


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
    return RedirectResponse(url="/admin?tab=users", status_code=303)


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
    return RedirectResponse(url="/admin?tab=users", status_code=303)


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
            return RedirectResponse(url="/admin?tab=groups&error=exists", status_code=303)
        db.add(Group(name=name))
        await db.commit()
    return RedirectResponse(url="/admin?tab=groups", status_code=303)


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
    return RedirectResponse(url="/admin?tab=groups", status_code=303)
