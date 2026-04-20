import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from temporalio.client import Client

import tasks  # noqa: F401 — trigger task registration
import workflows  # noqa: F401 — trigger workflow registration
from core.workflows import validate_assignments, validate_registrations
from ui.auth.csrf import get_csrf_token, set_csrf_cookie, validate_csrf
from core.db.engine import dispose_engine, get_session_factory, init_engine
from ui.auth.dependencies import LoginRequiredError
from ui.auth.routes import router as auth_router
from ui.auth.session import load_user_from_session
from ui.config import AppSettings
from ui.routers import admin, dashboard, task_detail, task_list, tasks, tasks_page, workflow_detail, workflows as workflows_router, workflows_list, ws
from core.db import DbService
from ui.services.temporal import TemporalService

logger = logging.getLogger(__name__)

_ui_dir = os.path.dirname(__file__)


validate_registrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AppSettings()
    app.state.settings = settings

    # Database
    init_engine(settings.database_url)
    db_service = DbService(get_session_factory())
    app.state.db_service = db_service

    # Ensure the admin group always exists
    try:
        await db_service.ensure_groups([settings.admin_group])
    except Exception:
        logger.warning("Could not create default groups (tables may not exist yet)", exc_info=True)

    # Seed default user if configured
    if settings.seed_username and settings.seed_password:
        seed_groups = [g.strip() for g in settings.seed_groups.split(",") if g.strip()]
        try:
            await db_service.seed_user(settings.seed_username, settings.seed_password, seed_groups)
        except Exception:
            logger.warning("Auto-seed failed (tables may not exist yet)", exc_info=True)

    # Purge expired sessions
    await db_service.delete_expired_sessions()

    # Validate workflow user/group assignments exist in the database
    await validate_assignments()

    # Temporal
    client = await Client.connect(settings.temporal_address)
    app.state.temporal_service = TemporalService(client, settings)
    app.state.templates = Jinja2Templates(directory=os.path.join(_ui_dir, "templates"))
    from core.tasks.registry import get_task_color, get_task_label
    app.state.templates.env.globals["get_task_color"] = get_task_color
    app.state.templates.env.globals["get_task_label"] = get_task_label

    yield

    await dispose_engine()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(_ui_dir, "static")), name="static")


@app.exception_handler(LoginRequiredError)
async def _login_required_handler(request, exc: LoginRequiredError):
    return RedirectResponse(url=exc.redirect_to, status_code=303)


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    """Enforce double-submit cookie CSRF on POST requests."""
    if request.method == "POST":
        # Skip CSRF for JSON API requests — protected by same-origin policy
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            if not await validate_csrf(request):
                return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)

    response = await call_next(request)

    # Set the CSRF cookie if a new token was generated during this request
    new_token = getattr(request.state, "_csrf_new_token", None)
    if new_token:
        set_csrf_cookie(response, new_token)

    return response


@app.middleware("http")
async def attach_user_to_request(request: Request, call_next):
    """Load the current user (if any) and attach to request.state for templates."""
    settings = getattr(getattr(request.app, "state", None), "settings", None)
    if settings:
        request.state.user = await load_user_from_session(
            request, settings.session_secret
        )
    else:
        request.state.user = None

    request.state.is_admin = (
        request.state.user is not None
        and request.state.user.is_admin
    )

    # Make CSRF token available via request.state for templates
    request.state.csrf_token = get_csrf_token(request)

    return await call_next(request)


app.include_router(auth_router)
app.include_router(dashboard.router)
app.include_router(tasks_page.router)
app.include_router(workflows_list.router)
app.include_router(task_list.router)
app.include_router(tasks.router)
app.include_router(workflows_router.router)
app.include_router(workflow_detail.router)
app.include_router(ws.router)
app.include_router(task_detail.router)
app.include_router(admin.router)
