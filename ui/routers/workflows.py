from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ui.dependencies import get_templates, get_temporal_service
from ui.helpers import validate_task_form
from ui.services.temporal import TemporalService
from core.workflows import get_all_workflows, get_workflow

router = APIRouter(tags=["workflows"])


@router.get("/start", response_class=HTMLResponse)
async def start_picker(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    wf_list = [
        {
            "key": w.key,
            "label": w.label,
            "description": w.description,
            "input_label": w.input_label,
            "input_placeholder": w.input_placeholder,
            "has_input_task": w.input_task is not None,
        }
        for w in get_all_workflows()
    ]
    return templates.TemplateResponse(
        "start_picker.html",
        {"request": request, "workflows": wf_list},
    )


@router.get("/start/{workflow_key}", response_class=HTMLResponse)
async def start_form(
    request: Request,
    workflow_key: str,
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    try:
        wf_def = get_workflow(workflow_key)
    except KeyError:
        return RedirectResponse(url="/start", status_code=303)

    form = None
    if wf_def.input_task:
        form = wf_def.input_task.Form()

    return templates.TemplateResponse(
        "start_workflow.html",
        {"request": request, "wf": wf_def, "form": form, "errors": {}},
    )


@router.post("/start/{workflow_key}", response_class=HTMLResponse)
async def start_submit(
    request: Request,
    workflow_key: str,
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    try:
        wf_def = get_workflow(workflow_key)
    except KeyError:
        return RedirectResponse(url="/start", status_code=303)

    form_data = await request.form()

    if wf_def.input_task:
        task = wf_def.input_task()
        form = wf_def.input_task.Form(form_data)

        model, errors = validate_task_form(task, form)
        if errors:
            return templates.TemplateResponse(
                "start_workflow.html",
                {"request": request, "wf": wf_def, "form": form, "errors": errors},
            )

        input_value = model
    else:
        input_value = form_data.get("input_value", "").strip()
        if not input_value:
            return templates.TemplateResponse(
                "start_workflow.html",
                {
                    "request": request,
                    "wf": wf_def,
                    "form": None,
                    "errors": {"input_value": ["This field is required."]},
                },
            )

    workflow_id = f"{workflow_key}-{uuid.uuid4().hex[:8]}"
    await service.start_workflow(wf_def, input_value, workflow_id)

    return RedirectResponse(url="/?started=1", status_code=303)
