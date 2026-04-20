"""Task detail page with comments and activity log."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_db_service, get_templates
from core.db import DbService

router = APIRouter(tags=["task_detail"], dependencies=[Depends(require_auth)])


def _format_dt(dt) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


@router.get("/tasks/{task_id}/detail", response_class=HTMLResponse)
async def task_detail(
    request: Request,
    task_id: str,
    db: DbService = Depends(get_db_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    """Full task detail page with metadata, comments, and activity log."""
    task = await db.get_task_by_id(task_id)
    if not task:
        return HTMLResponse("Task not found", status_code=404)

    user = getattr(request.state, "user", None)
    if user and not user.can_access_task(task.assigned_user or "", task.assigned_group or ""):
        return HTMLResponse("Access denied", status_code=403)

    comments = await db.get_task_comments(task_id)
    activity = await db.get_task_activity(task_id)

    # Determine valid status transitions
    from core.db.mixins.tasks import VALID_TRANSITIONS
    valid_transitions = list(VALID_TRANSITIONS.get(task.status, set()))

    return templates.TemplateResponse(
        "tasks/detail.html",
        {
            "request": request,
            "task": task,
            "comments": comments,
            "activity": activity,
            "valid_transitions": valid_transitions,
            "format_dt": _format_dt,
        },
    )


@router.post("/tasks/{task_id}/comments")
async def add_comment(
    request: Request,
    task_id: str,
    db: DbService = Depends(get_db_service),
) -> JSONResponse:
    """Add a comment to a task."""
    user = getattr(request.state, "user", None)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"}, status_code=401)

    task = await db.get_task_by_id(task_id)
    if not task:
        return JSONResponse({"ok": False, "error": "Task not found"}, status_code=404)

    if not user.can_access_task(task.assigned_user or "", task.assigned_group or ""):
        return JSONResponse({"ok": False, "error": "Access denied"}, status_code=403)

    body = await request.json()
    content = body.get("content", "").strip()
    is_internal = body.get("is_internal", False)

    if not content:
        return JSONResponse({"ok": False, "error": "Comment cannot be empty"}, status_code=400)

    comment = await db.add_task_comment(task_id, user.slug, content, is_internal)

    return JSONResponse({
        "ok": True,
        "comment": {
            "id": str(comment.id),
            "author": comment.author,
            "content": comment.content,
            "is_internal": comment.is_internal,
            "created_at": _format_dt(comment.created_at),
        },
    })
