from __future__ import annotations

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_auth
from ui.config import TAB_ORDER
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService
from core.workflows import get_all_workflows

router = APIRouter(tags=["task_list"], dependencies=[Depends(require_auth)])


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


@router.get("/", response_class=HTMLResponse)
async def task_list(
    request: Request,
    tab: str = Query("pending"),
    page: int = Query(1, ge=1),
    per_page: int | None = Query(None, ge=10, le=100),
    type: str | None = Query(None),
    q: str | None = Query(None),
    assignment: str | None = Query(None),
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    if tab not in TAB_ORDER:
        tab = "pending"

    wf_type = type or None
    search = q.strip() if q else None

    # Get current user info for assignment filtering
    user = getattr(request.state, "user", None)
    user_slug = user.slug if user else ""
    user_group_slugs = [g.slug for g in user.groups] if user else []

    if tab == "pending":
        list_coro = service.list_pending(
            page, wf_type, search, per_page=per_page,
            assignment=assignment,
            user_slug=user_slug,
            user_group_slugs=user_group_slugs,
        )
    else:
        list_coro = service.list_workflows(tab, page, wf_type, search, per_page=per_page)

    counts, result = await asyncio.gather(
        service.get_tab_counts(wf_type),
        list_coro,
    )

    items = [item.model_dump() for item in result.items]

    # Compute data hash for the client to compare against WS updates
    stable = [{k: v for k, v in it.items() if k not in ("started", "closed", "duration")} for it in items]
    data_hash = hashlib.md5(json.dumps({"counts": counts, "items": stable, "has_next": result.has_next}, sort_keys=True).encode()).hexdigest()

    return templates.TemplateResponse(
        "task_list.html",
        {
            "request": request,
            "items": items,
            "tab": tab,
            "tabs": TAB_ORDER,
            "counts": counts,
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
