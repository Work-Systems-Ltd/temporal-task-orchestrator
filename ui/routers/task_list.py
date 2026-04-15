from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ui.config import TAB_ORDER
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService
from workflows.registry import get_all_workflows

router = APIRouter(tags=["task_list"])


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


@router.get("/", response_class=HTMLResponse)
async def task_list(
    request: Request,
    tab: str = Query("pending"),
    page: int = Query(1, ge=1),
    type: str | None = Query(None),
    q: str | None = Query(None),
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    if tab not in TAB_ORDER:
        tab = "pending"

    wf_type = type or None
    search = q.strip() if q else None

    if tab == "pending":
        list_coro = service.list_pending(page, wf_type, search)
    else:
        list_coro = service.list_workflows(tab, page, wf_type, search)

    counts, result = await asyncio.gather(
        service.get_tab_counts(wf_type),
        list_coro,
    )

    return templates.TemplateResponse(
        "task_list.html",
        {
            "request": request,
            "items": [item.model_dump() for item in result.items],
            "tab": tab,
            "tabs": TAB_ORDER,
            "counts": counts,
            "page": page,
            "has_next": result.has_next,
            "has_prev": page > 1,
            "wf_type": wf_type,
            "search": search or "",
            "workflow_types": _get_workflow_types(),
        },
    )
