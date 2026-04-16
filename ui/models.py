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
    parent_id: str = ""
    children: list[dict] = []


class PendingTaskItem(BaseModel):
    workflow_id: str
    workflow_type: str | None = None
    task_type: str
    title: str
    description: str
    started: str
    status: str = "pending"
    parent_id: str = ""
    children: list[dict] = []


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
    duration: str = ""  # e.g. "120ms", "2.3s" — shown as badge


class TimelineStats(BaseModel):
    activity_time: str = ""  # total time in activities
    wait_time: str = ""  # total time waiting for human input
    total_time: str = ""  # end-to-end
    workflow_input: str = ""  # JSON string of workflow input
    workflow_output: str = ""  # JSON string of workflow result


class GraphNode(BaseModel):
    workflow_id: str
    workflow_type: str
    status: str  # "running", "completed", "failed", "pending"
    label: str
    is_current: bool = False  # True for the workflow being viewed


