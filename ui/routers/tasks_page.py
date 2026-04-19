from __future__ import annotations

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService
from core.workflows import get_all_workflows

router = APIRouter(tags=["tasks_page"], dependencies=[Depends(require_auth)])


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int | None = Query(None, ge=10, le=100),
    type: str | None = Query(None),
    q: str | None = Query(None),
    assignment: str | None = Query(None),
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    wf_type = type or None
    search = q.strip() if q else None

    user = getattr(request.state, "user", None)
    user_slug = user.slug if user else ""
    user_group_slugs = [g.slug for g in user.groups] if user else []

    result = await service.list_pending(
        page, wf_type, search, per_page=per_page,
        assignment=assignment,
        user_slug=user_slug,
        user_group_slugs=user_group_slugs,
    )

    items = [item.model_dump() for item in result.items]

    stable = [{k: v for k, v in it.items() if k not in ("started",)} for it in items]
    data_hash = hashlib.md5(json.dumps({"items": stable, "has_next": result.has_next}, sort_keys=True).encode()).hexdigest()

    return templates.TemplateResponse(
        "tasks_page.html",
        {
            "request": request,
            "items": items,
            "page": page,
            "has_next": result.has_next,
            "has_prev": page > 1,
            "per_page": per_page,
            "wf_type": wf_type,
            "search": search or "",
            "assignment": assignment or "",
            "workflow_types": _get_workflow_types(),
            "data_hash": data_hash,
        },
    )
