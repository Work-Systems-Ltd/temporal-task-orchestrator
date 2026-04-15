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
from human_tasks.registry import get_task
from workflows.approval import ApprovalWorkflow

temporal_client: Client | None = None


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


def _relative_time(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
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


@app.get("/", response_class=HTMLResponse)
async def task_list(request: Request):
    tasks = []
    total_running = 0
    async for wf in temporal_client.list_workflows('ExecutionStatus="Running"'):
        total_running += 1
        try:
            handle = temporal_client.get_workflow_handle(wf.id)
            raw = await handle.query("get_pending_task")
            if raw:
                meta = json.loads(raw)
                meta["workflow_id"] = wf.id
                meta["workflow_type"] = wf.workflow_type
                if wf.start_time:
                    meta["started"] = _relative_time(wf.start_time)
                else:
                    meta["started"] = "—"
                tasks.append(meta)
        except Exception:
            continue

    stats = {
        "pending": len(tasks),
        "running": total_running,
    }

    return templates.TemplateResponse(
        "task_list.html",
        {"request": request, "tasks": tasks, "stats": stats},
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
async def start_form(request: Request):
    return templates.TemplateResponse("start_workflow.html", {"request": request, "errors": {}})


@app.post("/start", response_class=HTMLResponse)
async def start_submit(request: Request):
    form_data = await request.form()
    description = form_data.get("description", "").strip()

    if not description:
        return templates.TemplateResponse(
            "start_workflow.html",
            {"request": request, "errors": {"description": ["Description is required."]}},
        )

    workflow_id = f"approval-{uuid.uuid4().hex[:8]}"
    await temporal_client.start_workflow(
        ApprovalWorkflow.run,
        description,
        id=workflow_id,
        task_queue="hello-world-task-queue",
    )

    return RedirectResponse(url="/?started=1", status_code=303)
