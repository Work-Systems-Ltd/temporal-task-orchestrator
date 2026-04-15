from fastapi import Request
from fastapi.templating import Jinja2Templates

from ui.services.temporal import TemporalService


def get_temporal_service(request: Request) -> TemporalService:
    return request.app.state.temporal_service


def get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates
