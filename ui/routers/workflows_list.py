from __future__ import annotations

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.config import WORKFLOW_TAB_ORDER
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService
from core.workflows import get_all_workflows

router = APIRouter(tags=["workflows_list"], dependencies=[Depends(require_auth)])


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(
    request: Request,
    tab: str = Query("running"),
    page: int = Query(1, ge=1),
    per_page: int | None = Query(None, ge=10, le=100),
    type: str | None = Query(None),
    q: str | None = Query(None),
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    if tab not in WORKFLOW_TAB_ORDER:
        tab = "running"

    wf_type = type or None
    search = q.strip() if q else None

    counts, result = await asyncio.gather(
        service.get_tab_counts(wf_type, tabs=WORKFLOW_TAB_ORDER),
        service.list_workflows(tab, page, wf_type, search, per_page=per_page),
    )

    items = [item.model_dump() for item in result.items]

    stable = [{k: v for k, v in it.items() if k not in ("started", "closed", "duration")} for it in items]
    data_hash = hashlib.md5(json.dumps({"counts": counts, "items": stable, "has_next": result.has_next}, sort_keys=True).encode()).hexdigest()

    return templates.TemplateResponse(
        "workflows_page.html",
        {
            "request": request,
            "items": items,
            "tab": tab,
            "tabs": WORKFLOW_TAB_ORDER,
            "counts": counts,
            "page": page,
            "has_next": result.has_next,
            "has_prev": page > 1,
            "per_page": per_page,
            "wf_type": wf_type,
            "search": search or "",
            "workflow_types": _get_workflow_types(),
            "data_hash": data_hash,
        },
    )
