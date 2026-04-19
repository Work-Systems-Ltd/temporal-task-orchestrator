from __future__ import annotations

import asyncio
import hashlib
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates

from ui.auth.dependencies import require_ws_auth
from ui.auth.models import User
from ui.config import TAB_ORDER, WORKFLOW_TAB_ORDER
from ui.dependencies import get_db_service, get_templates, get_temporal_service
from ui.services.db import DbService
from ui.services.temporal import TemporalService
from core.workflows import get_all_workflows

router = APIRouter()

logger = logging.getLogger(__name__)

PUSH_INTERVAL = 3


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


def _data_hash(counts: dict, items: list, has_next: bool) -> str:
    """Hash the actual data (ignoring time-formatted strings) to detect real changes."""
    stable_items = []
    for item in items:
        d = item.model_dump() if hasattr(item, "model_dump") else item
        stable = {k: v for k, v in d.items() if k not in ("started", "closed", "duration")}
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
    if tab not in WORKFLOW_TAB_ORDER:
        tab = "running"

    list_coro = service.list_workflows(tab, page, wf_type, search, per_page=per_page)

    counts, result = await asyncio.gather(
        service.get_tab_counts(wf_type, tabs=WORKFLOW_TAB_ORDER),
        list_coro,
    )

    items = result.items

    ctx = {
        "request": ws,
        "items": items,
        "tab": tab,
        "tabs": WORKFLOW_TAB_ORDER,
        "counts": counts,
        "page": page,
        "has_next": result.has_next,
        "has_prev": page > 1,
        "wf_type": wf_type,
        "search": search or "",
        "workflow_types": _get_workflow_types(),
    }

    tab_bar_html = ""
    for t in WORKFLOW_TAB_ORDER:
        active = "tab-item-active" if tab == t else ""
        count = counts.get(t, 0)
        badge = ""
        if count > 0:
            badge_cls = "count-badge-active" if tab == t else "count-badge-muted"
            badge = f'<span class="count-badge {badge_cls}">{count}</span>'
        tab_bar_html += (
            f'<a href="/workflows?tab={t}" @click="navigateTab($event)" '
            f'data-tab="{t}" class="tab-item {active}">'
            f'{t.capitalize()} {badge}</a>'
        )

    tab_content = templates.get_template("partials/tab_content.html").render(ctx)

    return {
        "tab_bar": tab_bar_html,
        "tab_content": tab_content,
        "hash": _data_hash(counts, items, result.has_next),
    }


@router.websocket("/ws/workflow/{workflow_id}")
async def workflow_detail_ws(
    ws: WebSocket,
    workflow_id: str,
    user: User = Depends(require_ws_auth),
    service: TemporalService = Depends(get_temporal_service),
) -> None:
    """Lightweight WS that pings the client when the workflow state changes."""
    await ws.accept()

    last_hash = ""

    async def push_loop() -> None:
        nonlocal last_hash
        while True:
            await asyncio.sleep(PUSH_INTERVAL)
            try:
                detail = await service.get_workflow_detail(workflow_id)
                if not detail:
                    continue
                # Hash key fields that indicate a meaningful change
                blob = json.dumps({
                    "status": detail.status,
                    "history_length": detail.history_length,
                    "run_id": detail.run_id,
                }, sort_keys=True)
                h = hashlib.md5(blob.encode()).hexdigest()
                if h != last_hash:
                    last_hash = h
                    await ws.send_json({"type": "refresh"})
            except WebSocketDisconnect:
                return
            except Exception:
                logger.exception("workflow_detail_ws push error")

    push_task = asyncio.create_task(push_loop())

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "submitted":
                # Task was just submitted — force a check after a short delay
                await asyncio.sleep(0.5)
                last_hash = ""
    except WebSocketDisconnect:
        pass
    finally:
        push_task.cancel()
        try:
            await push_task
        except asyncio.CancelledError:
            pass


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
        "tab": "running",
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


@router.websocket("/ws/task-list")
async def task_list_ws(
    ws: WebSocket,
    user: User = Depends(require_ws_auth),
    db: DbService = Depends(get_db_service),
) -> None:
    """Lightweight WS that pings the task list page when DB task data changes."""
    await ws.accept()

    last_hash = ""

    async def push_loop() -> None:
        nonlocal last_hash
        while True:
            await asyncio.sleep(PUSH_INTERVAL)
            try:
                counts = await db.count_tasks_by_status(
                    user_slug=user.slug,
                    user_group_slugs=user.group_slugs,
                    is_admin=user.is_admin,
                )
                blob = json.dumps(counts, sort_keys=True)
                h = hashlib.md5(blob.encode()).hexdigest()
                if h != last_hash:
                    last_hash = h
                    await ws.send_json({"type": "refresh"})
            except WebSocketDisconnect:
                return
            except Exception:
                logger.exception("task_list_ws push error")

    push_task = asyncio.create_task(push_loop())

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "nudge":
                last_hash = ""
    except WebSocketDisconnect:
        pass
    finally:
        push_task.cancel()
        try:
            await push_task
        except asyncio.CancelledError:
            pass
