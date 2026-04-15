from fastapi.templating import Jinja2Templates
from starlette.requests import HTTPConnection

from ui.services.temporal import TemporalService


def get_temporal_service(conn: HTTPConnection) -> TemporalService:
    return conn.app.state.temporal_service


def get_templates(conn: HTTPConnection) -> Jinja2Templates:
    return conn.app.state.templates
