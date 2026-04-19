from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ui.auth.dependencies import require_auth

router = APIRouter(tags=["redirects"])


@router.get("/")
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/tasks", status_code=303)
