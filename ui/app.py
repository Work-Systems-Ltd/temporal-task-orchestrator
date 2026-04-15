import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from temporalio.client import Client

import human_tasks.tasks  # noqa: F401
import workflows  # noqa: F401
from human_tasks.registry import get_task
from workflows.registry import get_all_workflows, get_workflow

temporal_client: Client | None = None

PAGE_SIZE = 20

STATUS_QUERIES = {
    "pending": 'ExecutionStatus="Running"',
    "running": 'ExecutionStatus="Running"',
    "completed": 'ExecutionStatus="Completed"',
    "failed": 'ExecutionStatus="Failed"',
    "cancelled": 'ExecutionStatus="Canceled"',
    "terminated": 'ExecutionStatus="Terminated"',
    "timed_out": 'ExecutionStatus="TimedOut"',
    "all": None,
}

TAB_ORDER = ["pending", "running", "completed", "failed", "all"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global temporal_client
    address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_client = await Client.connect(address)
    yield


app = FastAPI(lifespan=lifespan)

_ui_dir = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(_ui_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_ui_dir, "templates"))


def _relative_time(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _duration(start: datetime | None, end: datetime | None) -> str:
    if not start or not end:
        return "—"
    diff = end - start
    seconds = int(diff.total_seconds())
    if seconds < 1:
        return "<1s"
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m {seconds % 60}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"


def _status_name(status) -> str:
    if status is None:
        return "unknown"
    return status.name.lower().replace("_", " ")


def _build_query(base_query: str | None, wf_type: str | None) -> str | None:
    parts = []
    if base_query:
        parts.append(base_query)
    if wf_type:
        parts.append(f'WorkflowType="{wf_type}"')
    return " AND ".join(parts) if parts else None


async def _count_workflows(query: str | None) -> int:
    count = 0
    async for _ in temporal_client.list_workflows(query, page_size=100):
        count += 1
    return count


async def _count_pending(wf_type: str | None = None) -> int:
    count = 0
    query = 'ExecutionStatus="Running"'
    if wf_type:
        query += f' AND WorkflowType="{wf_type}"'
    async for wf in temporal_client.list_workflows(query, page_size=100):
        try:
            handle = temporal_client.get_workflow_handle(wf.id)
            raw = await handle.query("get_pending_task")
            if raw:
                count += 1
        except Exception:
            continue
    return count


async def _get_tab_counts(wf_type: str | None = None) -> dict[str, int]:
    counts = {}
    for tab in TAB_ORDER:
        if tab == "pending":
            counts[tab] = await _count_pending(wf_type)
        else:
            q = _build_query(STATUS_QUERIES[tab], wf_type)
            counts[tab] = await _count_workflows(q)
    return counts


async def _list_pending(page: int, wf_type: str | None = None) -> tuple[list[dict], bool]:
    all_pending = []
    query = 'ExecutionStatus="Running"'
    if wf_type:
        query += f' AND WorkflowType="{wf_type}"'
    async for wf in temporal_client.list_workflows(query):
        try:
            handle = temporal_client.get_workflow_handle(wf.id)
            raw = await handle.query("get_pending_task")
            if raw:
                meta = json.loads(raw)
                meta["workflow_id"] = wf.id
                meta["workflow_type"] = wf.workflow_type
                meta["started"] = _relative_time(wf.start_time)
                meta["status"] = "pending"
                all_pending.append(meta)
        except Exception:
            continue

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    items = all_pending[start:end]
    has_next = end < len(all_pending)
    return items, has_next


async def _list_workflows(tab: str, page: int, wf_type: str | None = None) -> tuple[list[dict], bool]:
    query = _build_query(STATUS_QUERIES.get(tab), wf_type)
    items = []
    skip = (page - 1) * PAGE_SIZE
    collected = 0
    skipped = 0

    async for wf in temporal_client.list_workflows(query, page_size=PAGE_SIZE * 2):
        if skipped < skip:
            skipped += 1
            continue

        if collected >= PAGE_SIZE + 1:
            break

        items.append({
            "workflow_id": wf.id,
            "workflow_type": wf.workflow_type or "—",
            "status": _status_name(wf.status),
            "started": _relative_time(wf.start_time),
            "closed": _relative_time(wf.close_time),
            "duration": _duration(wf.start_time, wf.close_time),
            "task_queue": wf.task_queue or "—",
        })
        collected += 1

    has_next = len(items) > PAGE_SIZE
    return items[:PAGE_SIZE], has_next


def _get_workflow_types() -> list[str]:
    return [wf.workflow_cls.__name__ for wf in get_all_workflows()]


@app.get("/", response_class=HTMLResponse)
async def task_list(request: Request):
    tab = request.query_params.get("tab", "pending")
    if tab not in TAB_ORDER:
        tab = "pending"

    page = int(request.query_params.get("page", "1"))
    if page < 1:
        page = 1

    wf_type = request.query_params.get("type") or None

    counts = await _get_tab_counts(wf_type)

    if tab == "pending":
        items, has_next = await _list_pending(page, wf_type)
    else:
        items, has_next = await _list_workflows(tab, page, wf_type)

    return templates.TemplateResponse(
        "task_list.html",
        {
            "request": request,
            "items": items,
            "tab": tab,
            "tabs": TAB_ORDER,
            "counts": counts,
            "page": page,
            "has_next": has_next,
            "has_prev": page > 1,
            "wf_type": wf_type,
            "workflow_types": _get_workflow_types(),
        },
    )


@app.get("/task/{workflow_id}", response_class=HTMLResponse)
async def task_form(request: Request, workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    raw = await handle.query("get_pending_task")
    if not raw:
        return RedirectResponse(url="/", status_code=303)

    meta = json.loads(raw)
    form_cls, _ = get_task(meta["task_type"])
    form = form_cls()

    return templates.TemplateResponse(
        "task_form.html",
        {
            "request": request,
            "form": form,
            "meta": meta,
            "workflow_id": workflow_id,
            "errors": {},
        },
    )


@app.post("/task/{workflow_id}", response_class=HTMLResponse)
async def task_submit(request: Request, workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    raw = await handle.query("get_pending_task")
    if not raw:
        return RedirectResponse(url="/", status_code=303)

    meta = json.loads(raw)
    form_cls, model_cls = get_task(meta["task_type"])

    form_data = await request.form()
    form = form_cls(form_data)

    if not form.validate():
        return templates.TemplateResponse(
            "task_form.html",
            {
                "request": request,
                "form": form,
                "meta": meta,
                "workflow_id": workflow_id,
                "errors": form.errors,
            },
        )

    try:
        model = model_cls(**{field.name: field.data for field in form})
    except ValidationError as exc:
        field_errors = {}
        for err in exc.errors():
            loc = err["loc"]
            field_name = str(loc[0]) if loc else "__root__"
            field_errors.setdefault(field_name, []).append(err["msg"])
        return templates.TemplateResponse(
            "task_form.html",
            {
                "request": request,
                "form": form,
                "meta": meta,
                "workflow_id": workflow_id,
                "errors": field_errors,
            },
        )

    await handle.signal("complete_human_task", model.model_dump_json())

    return RedirectResponse(url="/?completed=1", status_code=303)


@app.get("/start", response_class=HTMLResponse)
async def start_picker(request: Request):
    return templates.TemplateResponse(
        "start_picker.html",
        {"request": request, "workflows": get_all_workflows()},
    )


@app.get("/start/{workflow_key}", response_class=HTMLResponse)
async def start_form(request: Request, workflow_key: str):
    try:
        wf_def = get_workflow(workflow_key)
    except KeyError:
        return RedirectResponse(url="/start", status_code=303)

    return templates.TemplateResponse(
        "start_workflow.html",
        {"request": request, "wf": wf_def, "errors": {}},
    )


@app.post("/start/{workflow_key}", response_class=HTMLResponse)
async def start_submit(request: Request, workflow_key: str):
    try:
        wf_def = get_workflow(workflow_key)
    except KeyError:
        return RedirectResponse(url="/start", status_code=303)

    form_data = await request.form()
    input_value = form_data.get("input_value", "").strip()

    if not input_value:
        return templates.TemplateResponse(
            "start_workflow.html",
            {"request": request, "wf": wf_def, "errors": {"input_value": ["This field is required."]}},
        )

    workflow_id = f"{workflow_key}-{uuid.uuid4().hex[:8]}"
    await temporal_client.start_workflow(
        wf_def.workflow_cls.run,
        input_value,
        id=workflow_id,
        task_queue="hello-world-task-queue",
    )

    return RedirectResponse(url="/?started=1", status_code=303)
