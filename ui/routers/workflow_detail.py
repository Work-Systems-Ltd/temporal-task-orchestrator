from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService

router = APIRouter(tags=["workflow_detail"])


async def _noop() -> None:
    return None


@router.get("/workflow/{workflow_id}", response_class=HTMLResponse)
async def workflow_detail(
    request: Request,
    workflow_id: str,
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    detail = await service.get_workflow_detail(workflow_id)
    if not detail:
        return RedirectResponse(url="/", status_code=303)

    is_running = detail.status == "running"
    is_child = detail.parent_id is not None

    pending_task_result, timeline_result, graph = await asyncio.gather(
        service.get_pending_task(workflow_id) if is_running else _noop(),
        service.get_workflow_timeline(workflow_id),
        service.get_workflow_graph(workflow_id, detail),
    )

    pending_task = pending_task_result if is_running else None
    timeline, stats = timeline_result

    return templates.TemplateResponse(
        "workflow_detail.html",
        {
            "request": request,
            "detail": detail.model_dump(),
            "pending_task": pending_task.model_dump() if pending_task else None,
            "timeline": [e.model_dump() for e in timeline],
            "stats": stats.model_dump(),
            "graph": [n.model_dump() for n in graph],
            "is_child": is_child,
            "workflow_id": workflow_id,
        },
    )
