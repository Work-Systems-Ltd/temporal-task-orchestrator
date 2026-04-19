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
from ui.auth.database import dispose_engine, init_engine
from ui.auth.dependencies import LoginRequiredError
from ui.auth.routes import router as auth_router
from ui.auth.seed import ensure_default_groups, seed as seed_user
from ui.auth.session import delete_expired_sessions, load_user_from_session
from ui.config import AppSettings
from ui.routers import admin, task_list, tasks, tasks_page, workflow_detail, workflows as workflows_router, workflows_list, ws
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

    # Ensure the admin group always exists
    try:
        await ensure_default_groups(["admin"])
    except Exception:
        logger.warning("Could not create default groups (tables may not exist yet)", exc_info=True)

    # Seed default user if configured
    if settings.seed_username and settings.seed_password:
        seed_groups = [g.strip() for g in settings.seed_groups.split(",") if g.strip()]
        try:
            await seed_user(settings.seed_username, settings.seed_password, seed_groups)
        except Exception:
            logger.warning("Auto-seed failed (tables may not exist yet)", exc_info=True)

    # Purge expired sessions
    await delete_expired_sessions()

    # Validate workflow user/group assignments exist in the database
    await validate_assignments()

    # Temporal
    client = await Client.connect(settings.temporal_address)
    app.state.temporal_service = TemporalService(client, settings)
    app.state.templates = Jinja2Templates(directory=os.path.join(_ui_dir, "templates"))

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
        and any(g.name == "admin" for g in request.state.user.groups)
    )

    # Make CSRF token available via request.state for templates
    request.state.csrf_token = get_csrf_token(request)

    return await call_next(request)


app.include_router(auth_router)
app.include_router(tasks_page.router)
app.include_router(workflows_list.router)
app.include_router(task_list.router)
app.include_router(tasks.router)
app.include_router(workflows_router.router)
app.include_router(workflow_detail.router)
app.include_router(ws.router)
app.include_router(admin.router)
