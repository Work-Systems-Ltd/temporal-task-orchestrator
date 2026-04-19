from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_db_service, get_templates, get_temporal_service
from ui.models import AssigneeOption, AssigneesResponse, ReassignResult
from ui.services.db import DbService
from ui.services.temporal import TemporalService
from core.workflows import get_all_workflows

router = APIRouter(tags=["tasks_page"], dependencies=[Depends(require_auth)])


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int | None = Query(None, ge=10, le=100),
    type: str | None = Query(None),
    q: str | None = Query(None),
    assignment: str | None = Query(None),
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    wf_type = type
    search = q.strip() if q else None

    user = getattr(request.state, "user", None)
    user_slug = user.slug if user else ""
    user_group_slugs = user.group_slugs if user else []

    is_admin = user.is_admin if user else False

    result = await service.list_pending(
        page, wf_type, search, per_page=per_page,
        assignment=assignment,
        user_slug=user_slug,
        user_group_slugs=user_group_slugs,
        is_admin=is_admin,
    )

    items = result.items

    stable = [{k: v for k, v in it.model_dump().items() if k not in ("started",)} for it in items]
    data_hash = hashlib.md5(json.dumps({"items": stable, "has_next": result.has_next}, sort_keys=True).encode()).hexdigest()

    return templates.TemplateResponse(
        "tasks/list.html",
        {
            "request": request,
            "items": items,
            "page": page,
            "has_next": result.has_next,
            "has_prev": page > 1,
            "per_page": per_page,
            "wf_type": wf_type,
            "search": search or "",
            "assignment": assignment or "",
            "workflow_types": _get_workflow_types(),
            "data_hash": data_hash,
        },
    )


@router.get("/api/assignees")
async def get_assignees(
    request: Request,
    group: str | None = Query(None),
    db: DbService = Depends(get_db_service),
) -> JSONResponse:
    """Return users and groups the current user can reassign to.

    When ``group`` is provided, the user list is filtered to members of that group.
    """
    user = getattr(request.state, "user", None)
    if not user:
        return JSONResponse(AssigneesResponse(users=[], groups=[]).model_dump())

    if user.is_admin:
        raw_users = await db.get_assignable_users(group_slug=group)
        raw_groups = await db.get_assignable_groups()
        users = [AssigneeOption(**u) for u in raw_users]
        groups = [AssigneeOption(**g) for g in raw_groups]
    else:
        if group and group not in user.group_slugs:
            users = []
        else:
            users = [AssigneeOption(slug=user.slug, label=user.username)]
        groups = [AssigneeOption(slug=g.slug, label=g.name) for g in user.groups]

    return JSONResponse(AssigneesResponse(users=users, groups=groups).model_dump())


@router.post("/tasks/{workflow_id}/reassign")
async def reassign_task(
    request: Request,
    workflow_id: str,
    service: TemporalService = Depends(get_temporal_service),
) -> JSONResponse:
    user = getattr(request.state, "user", None)
    if not user:
        return JSONResponse(ReassignResult(ok=False, error="Not authenticated").model_dump(), status_code=401)

    # Verify user can access this task before allowing reassignment
    meta = await service.get_pending_task(workflow_id)
    if not meta:
        return JSONResponse(ReassignResult(ok=False, error="Task not found").model_dump(), status_code=404)
    if not user.can_access_task(meta.assigned_user, meta.assigned_group):
        return JSONResponse(ReassignResult(ok=False, error="Not allowed").model_dump(), status_code=403)

    body = await request.json()
    assigned_user = body.get("assigned_user", "")
    assigned_group = body.get("assigned_group", "")

    if not user.can_reassign_to(user_slug=assigned_user, group_slug=assigned_group):
        return JSONResponse(ReassignResult(ok=False, error="Not allowed").model_dump(), status_code=403)

    await service.reassign_task(workflow_id, assigned_user=assigned_user, assigned_group=assigned_group)
    return JSONResponse(ReassignResult(
        ok=True, assigned_user=assigned_user, assigned_group=assigned_group,
    ).model_dump())
