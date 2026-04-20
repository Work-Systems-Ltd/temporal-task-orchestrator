from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from ui.auth.dependencies import require_auth
from ui.dependencies import get_db_service, get_temporal_service
from ui.models import AssigneeOption, AssigneesResponse, ReassignResult
from ui.views.tasks import TaskTableView
from core.db import DbService
from ui.services.temporal import TemporalService

router = APIRouter(tags=["tasks_page"], dependencies=[Depends(require_auth)])

# Register the generic table view routes (GET /tasks + GET /api/tasks)
task_view = TaskTableView()
task_view.register(router)


# ── Non-list endpoints (kept as-is) ──


@router.get("/api/assignees")
async def get_assignees(
    request: Request,
    group: str | None = Query(None),
    db: DbService = Depends(get_db_service),
) -> JSONResponse:
    """Return users and groups the current user can reassign to."""
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

    await db.log_task_activity(
        task_id,
        action="status_changed",
        actor=user.slug,
        old_value=old_status,
        new_value=new_status,
    )

    return JSONResponse({"ok": True, "status": updated.status})
