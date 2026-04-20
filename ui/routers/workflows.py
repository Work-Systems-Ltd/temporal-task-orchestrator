from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_db_service, get_templates, get_temporal_service
from ui.helpers import validate_task_form
from ui.models import WorkflowPickerItem
from core.db import DbService
from ui.services.temporal import TemporalService
from core.workflows import get_all_workflows, get_workflow

router = APIRouter(tags=["workflows"], dependencies=[Depends(require_auth)])


@router.get("/start", response_class=HTMLResponse)
async def start_picker(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    user = getattr(request.state, "user", None)
    user_slug = user.slug if user else ""
    user_group_slugs = user.group_slugs if user else []
    is_admin = user.is_admin if user else False

    wf_list = [
        WorkflowPickerItem(
            key=w.key,
            label=w.label,
            description=w.description,
            input_label=w.input_label,
            input_placeholder=w.input_placeholder,
            has_input_task=w.input_task is not None,
        ).model_dump()
        for w in get_all_workflows()
        if w.can_access(user_slug, user_group_slugs, is_admin)
    ]
    return templates.TemplateResponse(
        "workflows/start_picker.html",
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

    user = getattr(request.state, "user", None)
    if not wf_def.can_access(
        user.slug if user else "",
        user.group_slugs if user else [],
        user.is_admin if user else False,
    ):
        return RedirectResponse(url="/start", status_code=303)

    form = None
    if wf_def.input_task:
        form = wf_def.input_task.Form()

    return templates.TemplateResponse(
        "workflows/start_form.html",
        {"request": request, "wf": wf_def, "form": form, "errors": {}},
    )


@router.post("/start/{workflow_key}", response_class=HTMLResponse)
async def start_submit(
    request: Request,
    workflow_key: str,
    service: TemporalService = Depends(get_temporal_service),
    db: DbService = Depends(get_db_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    try:
        wf_def = get_workflow(workflow_key)
    except KeyError:
        return RedirectResponse(url="/start", status_code=303)

    user = getattr(request.state, "user", None)
    if not wf_def.can_access(
        user.slug if user else "",
        user.group_slugs if user else [],
        user.is_admin if user else False,
    ):
        return RedirectResponse(url="/start", status_code=303)

    form_data = await request.form()

    if wf_def.input_task:
        task = wf_def.input_task()
        form = wf_def.input_task.Form(form_data)

        model, errors = await validate_task_form(task, form)
        if errors:
            return templates.TemplateResponse(
                "workflows/start_form.html",
                {"request": request, "wf": wf_def, "form": form, "errors": errors},
            )

        input_value = model
    else:
        input_value = form_data.get("input_value", "").strip()
        if not input_value:
            return templates.TemplateResponse(
                "workflows/start_form.html",
                {
                    "request": request,
                    "wf": wf_def,
                    "form": None,
                    "errors": {"input_value": ["This field is required."]},
                },
            )

    workflow_id = f"{workflow_key}-{uuid.uuid4().hex[:8]}"

    # Serialize input for DB storage
    input_dict = None
    if input_value is not None:
        if hasattr(input_value, "model_dump"):
            input_dict = input_value.model_dump()
        elif isinstance(input_value, dict):
            input_dict = input_value
        else:
            input_dict = {"value": input_value}

    await db.create_workflow_placeholder(
        workflow_id=workflow_id,
        workflow_key=workflow_key,
        workflow_type=wf_def.workflow_cls.__name__,
        started_by=user.slug if user else "",
        input_data=input_dict,
    )
    await service.start_workflow(wf_def, input_value, workflow_id)

    return RedirectResponse(url="/workflows?started=1", status_code=303)
