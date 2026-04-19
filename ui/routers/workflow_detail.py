from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_templates, get_temporal_service
from ui.helpers import validate_task_form
from ui.services.temporal import TemporalService

router = APIRouter(tags=["workflow_detail"], dependencies=[Depends(require_auth)])

RERUNNABLE_STATUSES = {"failed", "terminated", "timed_out", "cancelled"}


async def _noop() -> None:
    return None


@router.get("/workflow/{workflow_id}", response_class=HTMLResponse)
async def workflow_detail(
    request: Request,
    workflow_id: str,
    run_id: str | None = Query(None),
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    detail = await service.get_workflow_detail(workflow_id, run_id=run_id)
    if not detail:
        return RedirectResponse(url="/", status_code=303)

    is_running = detail.status == "running"
    is_child = detail.parent_id is not None

    timeline_result, graph, run_history = await asyncio.gather(
        service.get_workflow_timeline(workflow_id, run_id=run_id),
        service.get_workflow_graph(workflow_id, detail),
        service.get_run_history(workflow_id),
    )

    timeline, stats = timeline_result

    # Determine which run number this is (newest = 1)
    total_runs = len(run_history)
    current_run_id = detail.run_id
    run_number = next(
        (i + 1 for i, r in enumerate(run_history) if r["run_id"] == current_run_id),
        1,
    )

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
            "run_history": run_history,
            "run_number": run_number,
            "total_runs": total_runs,
        },
    )


@router.get("/workflow/{workflow_id}/rerun", response_class=HTMLResponse)
async def rerun_form(
    request: Request,
    workflow_id: str,
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    detail = await service.get_workflow_detail(workflow_id)
    if not detail or detail.status not in RERUNNABLE_STATUSES:
        return RedirectResponse(url=f"/workflow/{workflow_id}", status_code=303)

    wf_def = service.get_workflow_def_by_type(detail.workflow_type)
    if not wf_def:
        return RedirectResponse(url=f"/workflow/{workflow_id}", status_code=303)

    # Pre-populate the form with the original input
    original_input = await service.get_workflow_input(workflow_id)
    form = None
    if wf_def.input_task and original_input:
        form = wf_def.input_task.Form(data=original_input)
    elif wf_def.input_task:
        form = wf_def.input_task.Form()

    return templates.TemplateResponse(
        "rerun_workflow.html",
        {
            "request": request,
            "wf": wf_def,
            "form": form,
            "errors": {},
            "workflow_id": workflow_id,
            "original_input": original_input,
        },
    )


@router.post("/workflow/{workflow_id}/rerun", response_class=HTMLResponse, response_model=None)
async def rerun_submit(
    request: Request,
    workflow_id: str,
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse | RedirectResponse:
    detail = await service.get_workflow_detail(workflow_id)
    if not detail or detail.status not in RERUNNABLE_STATUSES:
        return RedirectResponse(url=f"/workflow/{workflow_id}", status_code=303)

    wf_def = service.get_workflow_def_by_type(detail.workflow_type)
    if not wf_def:
        return RedirectResponse(url=f"/workflow/{workflow_id}", status_code=303)

    form_data = await request.form()

    if wf_def.input_task:
        task = wf_def.input_task()
        form = wf_def.input_task.Form(form_data)

        model, errors = validate_task_form(task, form)
        if errors:
            return templates.TemplateResponse(
                "rerun_workflow.html",
                {
                    "request": request,
                    "wf": wf_def,
                    "form": form,
                    "errors": errors,
                    "workflow_id": workflow_id,
                    "original_input": None,
                },
            )
        input_value = model
    else:
        input_value = form_data.get("input_value", "").strip() or None

    await service.rerun_workflow(workflow_id, input_value=input_value)
    return RedirectResponse(url=f"/workflow/{workflow_id}", status_code=303)
