from __future__ import annotations

from pydantic import BaseModel, Field

from core.models import TaskMeta as TaskMeta  # re-export from shared location


class TaskListParams(BaseModel):
    tab: str = "pending"
    page: int = Field(default=1, ge=1)
    type: str | None = None
    q: str | None = None


class WorkflowItem(BaseModel):
    workflow_id: str
    workflow_type: str
    status: str
    started: str
    closed: str
    duration: str
    task_queue: str


class PendingTaskItem(BaseModel):
    workflow_id: str
    workflow_type: str | None = None
    task_type: str
    title: str
    description: str
    started: str
    status: str = "pending"


class PaginatedResult(BaseModel):
    items: list[WorkflowItem] | list[PendingTaskItem]
    has_next: bool


class WorkflowDetail(BaseModel):
    workflow_id: str
    run_id: str
    workflow_type: str
    status: str
    started: str
    closed: str
    duration: str
    task_queue: str
    history_length: int
    parent_id: str | None = None


class TimelineEvent(BaseModel):
    event_id: int
    event_time: str
    label: str
    status: str  # "completed", "failed", "pending", "info"
    detail: str = ""
    link: str = ""  # URL for clickable events (e.g. child workflows)


