import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from temporalio.client import Client

import human_tasks.tasks  # noqa: F401
import workflows  # noqa: F401
from ui.config import AppSettings
from workflows.registry import validate_registrations
from ui.routers import task_list, tasks, workflows as workflows_router, ws
from ui.services.temporal import TemporalService

_ui_dir = os.path.dirname(__file__)


validate_registrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AppSettings()
    client = await Client.connect(settings.temporal_address)
    app.state.temporal_service = TemporalService(client, settings)
    app.state.templates = Jinja2Templates(directory=os.path.join(_ui_dir, "templates"))
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(_ui_dir, "static")), name="static")
app.include_router(task_list.router)
app.include_router(tasks.router)
app.include_router(workflows_router.router)
app.include_router(ws.router)
