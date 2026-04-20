"""Dashboard with task metrics and summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_db_service, get_templates
from core.db import DbService

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_auth)])


def _relative_time(dt) -> str:
    """Return a human-friendly relative time string."""
    if dt is None:
        return ""
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    return dt.strftime("%Y-%m-%d %H:%M")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: DbService = Depends(get_db_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    summary = await db.get_task_summary_counts()
    overdue = await db.get_overdue_count()
    completed_today = await db.get_completed_count_since(today_start)
    completed_week = await db.get_completed_count_since(week_start)
    recent_activity = await db.get_recent_activity(limit=8)
    wf_counts = await db.count_workflows_by_status()
    running_workflows = wf_counts.get("running", 0)

    # My active tasks — actual records, not just counts
    user = request.state.user
    my_task_rows = []
    if user:
        my_task_rows, _ = await db.list_tasks(
            status="open",
            user_slug=user.slug,
            user_group_slugs=user.group_slugs,
            is_admin=user.is_admin,
            page=1,
            per_page=5,
            sort="created_at",
            order="desc",
        )
        # Also grab in_progress if we have room
        if len(my_task_rows) < 5:
            ip_rows, _ = await db.list_tasks(
                status="in_progress",
                user_slug=user.slug,
                user_group_slugs=user.group_slugs,
                is_admin=user.is_admin,
                page=1,
                per_page=5 - len(my_task_rows),
                sort="created_at",
                order="desc",
            )
            my_task_rows.extend(ip_rows)

    # Recently completed — pass user context for access control
    completed_rows, _ = await db.list_tasks(
        status="completed",
        user_slug=user.slug if user else "",
        user_group_slugs=user.group_slugs if user else None,
        is_admin=user.is_admin if user else False,
        page=1,
        per_page=5,
        sort="completed_at",
        order="desc",
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "summary": summary,
            "overdue": overdue,
            "completed_today": completed_today,
            "completed_week": completed_week,
            "recent_activity": recent_activity,
            "my_task_rows": my_task_rows,
            "completed_rows": completed_rows,
            "running_workflows": running_workflows,
            "relative_time": _relative_time,
        },
    )
