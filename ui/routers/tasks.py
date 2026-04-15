from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from human_tasks.registry import get_task
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService

router = APIRouter(tags=["tasks"])


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

    return templates.TemplateResponse(
        "task_form.html",
        {
            "request": request,
            "form": form,
            "meta": meta.model_dump(),
            "workflow_id": workflow_id,
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

    def _render_errors(errors: dict[str, list[str]]) -> HTMLResponse:
        return templates.TemplateResponse(
            "task_form.html",
            {
                "request": request,
                "form": form,
                "meta": meta.model_dump(),
                "workflow_id": workflow_id,
                "errors": errors,
            },
        )

    # WTForms validation
    if not form.validate():
        return _render_errors(form.errors)

    # Pydantic validation
    try:
        model = task.Model(**{field.name: field.data for field in form})
    except ValidationError as exc:
        field_errors: dict[str, list[str]] = {}
        for err in exc.errors():
            loc = err["loc"]
            field_name = str(loc[0]) if loc else "__root__"
            field_errors.setdefault(field_name, []).append(err["msg"])
        return _render_errors(field_errors)

    # Optional pre_submit validation
    pre_submit_errors = task.pre_submit(model)
    if pre_submit_errors:
        return _render_errors(pre_submit_errors)

    await service.signal_complete(workflow_id, model.model_dump_json())

    return RedirectResponse(url="/?completed=1", status_code=303)
