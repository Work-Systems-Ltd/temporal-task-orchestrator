from __future__ import annotations

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.config import WORKFLOW_TAB_ORDER
from ui.dependencies import get_db_service, get_templates
from ui.helpers import duration, relative_time
from ui.models import WorkflowListItem
from core.db import DbService
from core.workflows import get_all_workflows

router = APIRouter(tags=["workflows_list"], dependencies=[Depends(require_auth)])


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


def _record_to_item(record) -> WorkflowListItem:
    """Convert a WorkflowRecord ORM object to a WorkflowListItem pydantic model."""
    return WorkflowListItem(
        record_id=str(record.id),
        workflow_id=record.workflow_id,
        workflow_type=record.workflow_type,
        workflow_key=record.workflow_key,
        status=record.status if record.status != "starting" else "running",
        started=relative_time(record.created_at),
        closed=relative_time(record.closed_at),
        duration=duration(record.created_at, record.closed_at),
        started_by=record.started_by or "",
    )


@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(
    request: Request,
    tab: str = Query("running"),
    page: int = Query(1, ge=1),
    per_page: int | None = Query(None, ge=10, le=100),
    type: str | None = Query(None),
    q: str | None = Query(None),
    db: DbService = Depends(get_db_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    if tab not in WORKFLOW_TAB_ORDER:
        tab = "running"

    wf_type = type or None
    search = q.strip() if q else None
    size = per_page or 20

    counts, (rows, total) = await asyncio.gather(
        db.count_workflows_by_status(),
        db.list_workflows(
            status=tab,
            workflow_type=wf_type,
            search=search,
            page=page,
            per_page=size,
        ),
    )

    items = [_record_to_item(r) for r in rows]
    has_next = (page * size) < total

    stable = [{k: v for k, v in it.model_dump().items() if k not in ("started", "closed", "duration")} for it in items]
    data_hash = hashlib.md5(json.dumps({"counts": counts, "items": stable, "has_next": has_next}, sort_keys=True).encode()).hexdigest()

    return templates.TemplateResponse(
        "workflows/list.html",
        {
            "request": request,
            "items": items,
            "tab": tab,
            "tabs": WORKFLOW_TAB_ORDER,
            "counts": counts,
            "page": page,
            "has_next": has_next,
            "has_prev": page > 1,
            "per_page": per_page,
            "wf_type": wf_type,
            "search": search or "",
            "workflow_types": _get_workflow_types(),
            "data_hash": data_hash,
        },
    )
