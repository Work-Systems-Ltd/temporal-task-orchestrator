from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse

from ui.auth.dependencies import require_admin
from ui.dependencies import get_db_service
from ui.views.admin import GroupTableView, UserTableView
from core.db import DbService

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])

# Register the generic table view routes
# GET /admin/users + GET /api/admin/users
user_view = UserTableView()
user_view.register(router)

# GET /admin/groups + GET /api/admin/groups
group_view = GroupTableView()
group_view.register(router)


# ---------------------------------------------------------------------------
# Redirect /admin → /admin/users (default landing)
# ---------------------------------------------------------------------------

@router.get("/admin")
@router.get("/admin/")
async def admin_redirect() -> RedirectResponse:
    return RedirectResponse(url="/admin/users", status_code=303)


# ---------------------------------------------------------------------------
# User actions
# ---------------------------------------------------------------------------

@router.post("/admin/users/add")
async def user_add(
    username: str = Form(...),
    display_name: str = Form(""),
    password: str = Form(...),
    group_ids: list[str] = Form(default=[]),
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    user = await db.create_user(username, password, display_name, group_ids)
    if not user:
        return RedirectResponse(url="/admin/users?error=exists", status_code=303)
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/admin/users/{user_id}/reset-password")
async def user_reset_password(
    user_id: str,
    password: str = Form(...),
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    await db.reset_password(user_id, password)
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/admin/users/{user_id}/delete")
async def user_delete(
    request: Request,
    user_id: str,
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    current_user = request.state.user
    if str(current_user.id) != user_id:
        await db.delete_user(user_id)
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/admin/users/{user_id}/groups")
async def user_update_groups(
    user_id: str,
    group_ids: list[str] = Form(default=[]),
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    await db.update_user_groups(user_id, group_ids)
    return RedirectResponse(url="/admin/users", status_code=303)


# ---------------------------------------------------------------------------
# Group actions
# ---------------------------------------------------------------------------

@router.post("/admin/groups/add")
async def group_add(
    name: str = Form(...),
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    group = await db.create_group(name)
    if not group:
        return RedirectResponse(url="/admin/groups?error=exists", status_code=303)
    return RedirectResponse(url="/admin/groups", status_code=303)


@router.post("/admin/groups/{group_id}/delete")
async def group_delete(
    group_id: str,
    db: DbService = Depends(get_db_service),
) -> RedirectResponse:
    await db.delete_group(group_id)
    return RedirectResponse(url="/admin/groups", status_code=303)
