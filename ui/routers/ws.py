from __future__ import annotations

import asyncio
import hashlib
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_ws_auth
from ui.auth.models import User
from ui.config import TAB_ORDER
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService
from core.workflows import get_all_workflows

router = APIRouter()

logger = logging.getLogger(__name__)

PUSH_INTERVAL = 3


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


def _data_hash(counts: dict, items: list[dict], has_next: bool) -> str:
    """Hash the actual data (ignoring time-formatted strings) to detect real changes."""
    stable_items = []
    for item in items:
        stable = {k: v for k, v in item.items() if k not in ("started", "closed", "duration")}
        stable_items.append(stable)
    blob = json.dumps({"counts": counts, "items": stable_items, "has_next": has_next}, sort_keys=True)
    return hashlib.md5(blob.encode()).hexdigest()


async def _build_update(
    ws: WebSocket,
    templates: Jinja2Templates,
    service: TemporalService,
    tab: str,
    page: int,
    wf_type: str | None,
    search: str | None,
    per_page: int | None = None,
) -> dict:
    """Build a full update payload with rendered fragments and data hash."""
    if tab not in TAB_ORDER:
        tab = "pending"

    if tab == "pending":
        list_coro = service.list_pending(page, wf_type, search, per_page=per_page)
    else:
        list_coro = service.list_workflows(tab, page, wf_type, search, per_page=per_page)

    counts, result = await asyncio.gather(
        service.get_tab_counts(wf_type),
        list_coro,
    )

    items = [item.model_dump() for item in result.items]

    ctx = {
        "request": ws,
        "items": items,
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

    return {
        "tab_bar": tab_bar,
        "tab_content": tab_content,
        "hash": _data_hash(counts, items, result.has_next),
    }


@router.websocket("/ws/tasks")
async def tasks_ws(
    ws: WebSocket,
    user: User = Depends(require_ws_auth),
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> None:
    await ws.accept()

    # Shared state — only modified by the receive loop, read by push_loop
    state = {
        "tab": "pending",
        "page": 1,
        "per_page": None,
        "wf_type": None,
        "search": None,
        "seq": 0,
    }
    last_hash = ""
    # Event fired to wake push_loop immediately (on navigation or visibility)
    nudge = asyncio.Event()

    async def push_loop() -> None:
        nonlocal last_hash
        while True:
            # Wait for either the interval or a nudge
            try:
                await asyncio.wait_for(nudge.wait(), timeout=PUSH_INTERVAL)
                nudge.clear()
                # On nudge, always push (even if hash matches) for responsiveness
                force = True
            except asyncio.TimeoutError:
                force = False

            try:
                payload = await _build_update(
                    ws, templates, service,
                    state["tab"], state["page"],
                    state["wf_type"], state["search"],
                    per_page=state["per_page"],
                )
                if force or payload["hash"] != last_hash:
                    last_hash = payload["hash"]
                    await ws.send_json({
                        "type": "update",
                        "seq": state["seq"],
                        "hash": payload["hash"],
                        "tab_bar": payload["tab_bar"],
                        "tab_content": payload["tab_content"],
                    })
            except WebSocketDisconnect:
                return
            except Exception:
                logger.exception("push_loop error")

    push_task = asyncio.create_task(push_loop())

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "view":
                state["tab"] = msg.get("tab", "pending")
                state["page"] = max(1, int(msg.get("page", 1)))
                raw_per_page = msg.get("per_page")
                state["per_page"] = max(10, min(100, int(raw_per_page))) if raw_per_page is not None else None
                state["wf_type"] = msg.get("wf_type") or None
                state["search"] = msg.get("search") or None
                state["seq"] = int(msg.get("seq", 0))
                last_hash = ""  # force update on navigation
                nudge.set()

            elif msg_type == "visible":
                # Tab became visible again — force a fresh push
                last_hash = ""
                nudge.set()

    except WebSocketDisconnect:
        pass
    finally:
        push_task.cancel()
        try:
            await push_task
        except asyncio.CancelledError:
            pass
