from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates

from ui.config import TAB_ORDER
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService
from workflows.registry import get_all_workflows

router = APIRouter()

PUSH_INTERVAL = 3


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


async def _render_fragments(
    ws: WebSocket,
    templates: Jinja2Templates,
    service: TemporalService,
    tab: str,
    page: int,
    wf_type: str | None,
    search: str | None,
) -> dict[str, str]:
    """Render the tab-bar and tab-content HTML fragments for a push."""
    if tab not in TAB_ORDER:
        tab = "pending"

    if tab == "pending":
        list_coro = service.list_pending(page, wf_type, search)
    else:
        list_coro = service.list_workflows(tab, page, wf_type, search)

    counts, result = await asyncio.gather(
        service.get_tab_counts(wf_type),
        list_coro,
    )

    ctx = {
        "request": ws,
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
    }

    tab_bar = templates.get_template("partials/tab_bar.html").render(ctx)
    tab_content = templates.get_template("partials/tab_content.html").render(ctx)

    return {"tab_bar": tab_bar, "tab_content": tab_content}


@router.websocket("/ws/tasks")
async def tasks_ws(
    ws: WebSocket,
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> None:
    await ws.accept()

    # Default view params — client sends updates when user navigates
    tab = "pending"
    page = 1
    wf_type: str | None = None
    search: str | None = None

    async def push_loop() -> None:
        nonlocal tab, page, wf_type, search
        while True:
            try:
                fragments = await _render_fragments(
                    ws, templates, service, tab, page, wf_type, search,
                )
                await ws.send_json({"type": "update", **fragments})
            except WebSocketDisconnect:
                return
            except Exception:
                pass
            await asyncio.sleep(PUSH_INTERVAL)

    push_task = asyncio.create_task(push_loop())

    try:
        while True:
            msg = await ws.receive_json()
            # Client sends view params when user changes tab/page/filter
            if msg.get("type") == "view":
                tab = msg.get("tab", "pending")
                page = max(1, int(msg.get("page", 1)))
                wf_type = msg.get("wf_type") or None
                search = msg.get("search") or None
                # Immediately push after view change
                try:
                    fragments = await _render_fragments(
                        ws, templates, service, tab, page, wf_type, search,
                    )
                    await ws.send_json({"type": "update", **fragments})
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        push_task.cancel()
        try:
            await push_task
        except asyncio.CancelledError:
            pass
