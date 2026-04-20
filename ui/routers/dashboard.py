"""Dashboard with task metrics and summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_db_service, get_templates, get_temporal_service
from ui.services.db import DbService
from ui.services.temporal import TemporalService

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_auth)])


def _format_dt(dt) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


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
    return _format_dt(dt)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: DbService = Depends(get_db_service),
    temporal: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    # Gather all metrics
    summary = await db.get_task_summary_counts()
    overdue = await db.get_overdue_count()
    completed_today = await db.get_completed_count_since(today_start)
    completed_week = await db.get_completed_count_since(week_start)

    # Recent activity across all tasks
    recent_activity = await db.get_recent_activity(limit=8)

    # My tasks (current user)
    user = request.state.user
    my_tasks: dict[str, int] = {}
    if user:
        my_tasks = await db.count_tasks_by_status(
            user_slug=user.slug,
            user_group_slugs=user.group_slugs,
            is_admin=user.is_admin,
        )

    # Running workflows
    running_workflows = await temporal.count_pending()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "summary": summary,
            "overdue": overdue,
            "completed_today": completed_today,
            "completed_week": completed_week,
            "recent_activity": recent_activity,
            "my_tasks": my_tasks,
            "running_workflows": running_workflows,
            "format_dt": _format_dt,
            "relative_time": _relative_time,
        },
    )
