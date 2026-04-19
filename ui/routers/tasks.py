from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.tasks import get_task
from ui.auth.dependencies import require_auth
from ui.dependencies import get_templates, get_temporal_service
from ui.helpers import validate_task_form
from ui.services.temporal import TemporalService

router = APIRouter(tags=["tasks"], dependencies=[Depends(require_auth)])


@router.get("/task/{workflow_id}", response_class=HTMLResponse)
async def task_form(
    request: Request,
    workflow_id: str,
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    meta = await service.get_pending_task(workflow_id)
    if not meta:
        return RedirectResponse(url="/", status_code=303)

    task = get_task(meta.task_type)
    form = task.Form()

    detail = await service.get_workflow_detail(workflow_id)
    wf_type = detail.workflow_type if detail else ""

    return templates.TemplateResponse(
        "task_form.html",
        {
            "request": request,
            "form": form,
            "meta": meta.model_dump(),
            "workflow_id": workflow_id,
            "workflow_type": wf_type,
            "errors": {},
        },
    )


@router.post("/task/{workflow_id}", response_class=HTMLResponse)
async def task_submit(
    request: Request,
    workflow_id: str,
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    meta = await service.get_pending_task(workflow_id)
    if not meta:
        return RedirectResponse(url="/", status_code=303)

    task = get_task(meta.task_type)

    form_data = await request.form()
    form = task.Form(form_data)

    detail = await service.get_workflow_detail(workflow_id)
    wf_type = detail.workflow_type if detail else ""

    def _render_errors(errors: dict[str, list[str]]) -> HTMLResponse:
        return templates.TemplateResponse(
            "task_form.html",
            {
                "request": request,
                "form": form,
                "meta": meta.model_dump(),
                "workflow_id": workflow_id,
                "workflow_type": wf_type,
                "errors": errors,
            },
        )

    model, errors = validate_task_form(task, form)
    if errors:
        return _render_errors(errors)

    await service.signal_complete(workflow_id, model.model_dump_json())

    return RedirectResponse(url="/?completed=1", status_code=303)
