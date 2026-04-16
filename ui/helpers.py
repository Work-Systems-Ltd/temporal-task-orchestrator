from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from core.tasks.base import HumanTask, TaskForm


def relative_time(dt: datetime | None) -> str:
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


def duration(start: datetime | None, end: datetime | None) -> str:
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


def status_name(status: object) -> str:
    if status is None:
        return "unknown"
    return status.name.lower().replace("_", " ")


def validate_task_form(
    task: HumanTask, form: TaskForm,
) -> tuple[BaseModel | None, dict[str, list[str]]]:
    """Run WTForms → Pydantic → pre_submit validation pipeline.

    Returns (model, errors). If model is not None, validation passed.
    """
    if not form.validate():
        return None, form.errors

    try:
        model = form.to_model(task.Model)
    except ValidationError as exc:
        field_errors: dict[str, list[str]] = {}
        for err in exc.errors():
            loc = err["loc"]
            field_name = str(loc[0]) if loc else "__root__"
            field_errors.setdefault(field_name, []).append(err["msg"])
        return None, field_errors

    pre_submit_errors = task.pre_submit(model)
    if pre_submit_errors:
        return None, pre_submit_errors

    return model, {}
