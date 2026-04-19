from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_admin
from ui.dependencies import get_db_service, get_templates
from ui.services.db import DbService

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
    db: DbService = Depends(get_db_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    search = q.strip() if q else None
    users = await db.list_users(search=search if tab == "users" else None)
    groups = await db.list_groups(search=search if tab == "groups" else None)
    user_count = await db.count_users()
    group_count = await db.count_groups()

    return templates.TemplateResponse(
        "auth/admin.html",
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
    username: str = Form(...),
    display_name: str = Form(""),
    password: str = Form(...),
    group_ids: list[str] = Form(default=[]),
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    user = await db.create_user(username, password, display_name, group_ids)
    if not user:
        return RedirectResponse(url="/admin?tab=users&error=exists", status_code=303)
    return RedirectResponse(url="/admin?tab=users", status_code=303)


@router.post("/users/{user_id}/reset-password")
async def user_reset_password(
    user_id: str,
    password: str = Form(...),
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    await db.reset_password(user_id, password)
    return RedirectResponse(url="/admin?tab=users", status_code=303)


@router.post("/users/{user_id}/delete")
async def user_delete(
    request: Request,
    user_id: str,
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    current_user = request.state.user
    if str(current_user.id) != user_id:
        await db.delete_user(user_id)
    return RedirectResponse(url="/admin?tab=users", status_code=303)


@router.post("/users/{user_id}/groups")
async def user_update_groups(
    user_id: str,
    group_ids: list[str] = Form(default=[]),
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    await db.update_user_groups(user_id, group_ids)
    return RedirectResponse(url="/admin?tab=users", status_code=303)


# ---------------------------------------------------------------------------
# Group actions
# ---------------------------------------------------------------------------

@router.post("/groups/add")
async def group_add(
    name: str = Form(...),
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    group = await db.create_group(name)
    if not group:
        return RedirectResponse(url="/admin?tab=groups&error=exists", status_code=303)
    return RedirectResponse(url="/admin?tab=groups", status_code=303)


@router.post("/groups/{group_id}/delete")
async def group_delete(
    group_id: str,
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    await db.delete_group(group_id)
    return RedirectResponse(url="/admin?tab=groups", status_code=303)
