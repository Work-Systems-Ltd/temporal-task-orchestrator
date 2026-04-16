from __future__ import annotations

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates

from ui.config import TAB_ORDER
from ui.dependencies import get_templates, get_temporal_service
from ui.services.temporal import TemporalService
from workflows.registry import get_all_workflows

router = APIRouter()

PUSH_INTERVAL = 3


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


def _data_hash(counts: dict, items: list[dict], has_next: bool) -> str:
    """Hash the actual data (ignoring time-formatted strings) to detect real changes."""
    # Strip time-display fields that change every render
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
    service: TemporalService = Depends(get_temporal_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> None:
    await ws.accept()

    tab = "pending"
    page = 1
    per_page: int | None = None
    wf_type: str | None = None
    search: str | None = None
    seq = 0
    last_hash = ""

    async def push_loop() -> None:
        nonlocal tab, page, per_page, wf_type, search, seq, last_hash
        while True:
            snap_seq = seq
            snap_tab = tab
            snap_page = page
            snap_per_page = per_page
            snap_wf_type = wf_type
            snap_search = search
            try:
                payload = await _build_update(
                    ws, templates, service,
                    snap_tab, snap_page, snap_wf_type, snap_search,
                    per_page=snap_per_page,
                )
                # Only push if data actually changed
                if payload["hash"] != last_hash:
                    last_hash = payload["hash"]
                    await ws.send_json({
                        "type": "update",
                        "seq": snap_seq,
                        "tab_bar": payload["tab_bar"],
                        "tab_content": payload["tab_content"],
                    })
            except WebSocketDisconnect:
                return
            except Exception:
                pass
            await asyncio.sleep(PUSH_INTERVAL)

    push_task = asyncio.create_task(push_loop())

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "view":
                tab = msg.get("tab", "pending")
                page = max(1, int(msg.get("page", 1)))
                raw_per_page = msg.get("per_page")
                per_page = max(10, min(100, int(raw_per_page))) if raw_per_page is not None else None
                wf_type = msg.get("wf_type") or None
                search = msg.get("search") or None
                seq = int(msg.get("seq", 0))
                # Always push immediately on navigation (user expects visual feedback)
                try:
                    payload = await _build_update(
                        ws, templates, service, tab, page, wf_type, search,
                        per_page=per_page,
                    )
                    last_hash = payload["hash"]
                    await ws.send_json({
                        "type": "update",
                        "seq": seq,
                        "tab_bar": payload["tab_bar"],
                        "tab_content": payload["tab_content"],
                    })
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
