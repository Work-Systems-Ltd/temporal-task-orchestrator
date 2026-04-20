from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.config import TASK_PRIORITY_ORDER, TASK_SORT_OPTIONS, TASK_TAB_LABELS, TASK_TAB_ORDER
from ui.dependencies import get_db_service, get_templates, get_temporal_service
from ui.models import AssigneeOption, AssigneesResponse, ReassignResult, TaskListItem
from core.db import DbService
from ui.services.temporal import TemporalService

router = APIRouter(tags=["tasks_page"], dependencies=[Depends(require_auth)])


def _format_dt(dt) -> str:
    """Format a datetime for display, or return empty string."""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def _task_record_to_item(record) -> TaskListItem:
    """Convert a TaskRecord ORM object to a TaskListItem."""
    return TaskListItem(
        task_id=str(record.id),
        workflow_id=record.workflow_id,
        task_type=record.task_type,
        title=record.title,
        description=record.description or "",
        status=record.status,
        priority=record.priority,
        assigned_user=record.assigned_user or "",
        assigned_group=record.assigned_group or "",
        created_by=record.created_by or "",
        completed_by=record.completed_by or "",
        created_at=_format_dt(record.created_at),
        updated_at=_format_dt(record.updated_at),
        completed_at=_format_dt(record.completed_at),
        due_at=_format_dt(record.due_at),
    )


@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    tab: str = Query("open"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
    type: str | None = Query(None),
    q: str | None = Query(None),
    assignment: str | None = Query(None),
    priority: str | None = Query(None),
    sort_by: str | None = Query(None),
    db: DbService = Depends(get_db_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    task_type = type
    search = q.strip() if q else None

    user = getattr(request.state, "user", None)
    user_slug = user.slug if user else ""
    user_group_slugs = user.group_slugs if user else []
    is_admin = user.is_admin if user else False

    # Parse sort parameter (format: "field:direction")
    sort_field = "created_at"
    sort_order = "desc"
    if sort_by and ":" in sort_by:
        parts = sort_by.split(":", 1)
        sort_field = parts[0]
        sort_order = parts[1]

    # Determine assignment filter
    filter_user = None
    filter_group = None
    if assignment == "mine":
        filter_user = user_slug
    elif assignment == "my_groups" and user_group_slugs:
        # We'll handle multi-group in the query; for now filter by first group
        filter_group = user_group_slugs[0] if len(user_group_slugs) == 1 else None

    # Query tasks from DB
    records, total = await db.list_tasks(
        status=tab if tab != "all" else None,
        task_type=task_type,
        assigned_user=filter_user,
        assigned_group=filter_group,
        priority=priority,
        search=search,
        user_slug=user_slug,
        user_group_slugs=user_group_slugs,
        is_admin=is_admin,
        page=page,
        per_page=per_page,
        sort=sort_field,
        order=sort_order,
    )

    items = [_task_record_to_item(r) for r in records]

    # Get tab counts
    tab_counts = await db.count_tasks_by_status(
        user_slug=user_slug,
        user_group_slugs=user_group_slugs,
        is_admin=is_admin,
    )

    # Get distinct task types for filter dropdown
    task_types = await db.get_distinct_task_types()

    has_next = (page * per_page) < total
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    # Data hash for WebSocket change detection
    stable = [it.model_dump() for it in items]
    data_hash = hashlib.md5(
        json.dumps({"items": stable, "total": total}, sort_keys=True).encode()
    ).hexdigest()

    return templates.TemplateResponse(
        "tasks/list.html",
        {
            "request": request,
            "items": items,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": page > 1,
            "per_page": per_page,
            "tab": tab,
            "tab_order": TASK_TAB_ORDER,
            "tab_labels": TASK_TAB_LABELS,
            "tab_counts": tab_counts,
            "task_type": task_type,
            "task_types": task_types,
            "search": search or "",
            "assignment": assignment or "",
            "priority": priority or "",
            "priority_options": TASK_PRIORITY_ORDER,
            "sort_by": sort_by or "created_at:desc",
            "sort_options": TASK_SORT_OPTIONS,
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
    db: DbService = Depends(get_db_service),
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

    # Sync reassignment to the database task record
    task_record = await db.get_task_by_workflow_id(workflow_id)
    if task_record:
        await db.update_task_assignment(
            str(task_record.id),
            assigned_user=assigned_user,
            assigned_group=assigned_group,
        )
        await db.log_task_activity(
            str(task_record.id),
            action="reassigned",
            actor=user.slug,
            old_value=f"{meta.assigned_user or ''}/{meta.assigned_group or ''}",
            new_value=f"{assigned_user or ''}/{assigned_group or ''}",
        )

    return JSONResponse(ReassignResult(
        ok=True, assigned_user=assigned_user, assigned_group=assigned_group,
    ).model_dump())


@router.post("/tasks/{task_id}/status")
async def update_task_status(
    request: Request,
    task_id: str,
    db: DbService = Depends(get_db_service),
) -> JSONResponse:
    """Transition a task to a new status."""
    user = getattr(request.state, "user", None)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"}, status_code=401)

    body = await request.json()
    new_status = body.get("status", "")

    if not new_status:
        return JSONResponse({"ok": False, "error": "Missing status"}, status_code=400)

    # Check access
    task = await db.get_task_by_id(task_id)
    if not task:
        return JSONResponse({"ok": False, "error": "Task not found"}, status_code=404)
    if not user.can_access_task(task.assigned_user or "", task.assigned_group or ""):
        return JSONResponse({"ok": False, "error": "Not allowed"}, status_code=403)

    old_status = task.status
    updated = await db.update_task_status(task_id, new_status, actor=user.slug)
    if not updated:
        return JSONResponse(
            {"ok": False, "error": f"Invalid status transition from '{old_status}' to '{new_status}'"},
            status_code=400,
        )

    # Log the status change
    await db.log_task_activity(
        task_id,
        action="status_changed",
        actor=user.slug,
        old_value=old_status,
        new_value=new_status,
    )

    return JSONResponse({"ok": True, "status": updated.status})
