from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService

router = APIRouter(tags=["workflow_detail"], dependencies=[Depends(require_auth)])

RERUNNABLE_STATUSES = {"failed", "terminated", "timed_out", "cancelled"}


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

    timeline_result, graph = await asyncio.gather(
        service.get_workflow_timeline(workflow_id),
        service.get_workflow_graph(workflow_id, detail),
    )

    timeline, stats = timeline_result

    # Collect pending tasks from this workflow + all descendants
    pending_tasks = await service.get_all_pending_tasks(graph, workflow_id) if is_running else []

    return templates.TemplateResponse(
        "workflow_detail.html",
        {
            "request": request,
            "detail": detail.model_dump(),
            "pending_tasks": pending_tasks,
            "timeline": [e.model_dump() for e in timeline],
            "stats": stats.model_dump(),
            "graph": graph.model_dump() if graph else None,
            "is_child": is_child,
            "workflow_id": workflow_id,
            "can_rerun": detail.status in RERUNNABLE_STATUSES,
        },
    )


@router.post("/workflow/{workflow_id}/rerun")
async def rerun_workflow(
    workflow_id: str,
    service: TemporalService = Depends(get_temporal_service),
) -> RedirectResponse:
    try:
        await service.rerun_workflow(workflow_id)
    except ValueError:
        pass  # Redirect back regardless — UI will show updated status
    return RedirectResponse(url=f"/workflow/{workflow_id}", status_code=303)
