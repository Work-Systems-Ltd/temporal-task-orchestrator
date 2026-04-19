"""Dashboard with task metrics and summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_db_service, get_templates
from ui.services.db import DbService

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_auth)])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: DbService = Depends(get_db_service),
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

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "summary": summary,
            "overdue": overdue,
            "completed_today": completed_today,
            "completed_week": completed_week,
        },
    )
