from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from core.models import TaskMeta as TaskMeta  # re-export from shared location


# ── Request params ──

class TaskListParams(BaseModel):
    tab: str = "pending"
    page: int = Field(default=1, ge=1)
    type: str | None = None
    q: str | None = None


# ── Workflow items (list views) ──

class WorkflowItem(BaseModel):
    workflow_id: str
    workflow_type: str
    status: str
    started: str
    closed: str
    duration: str
    task_queue: str
    run_id: str = ""
    history_length: int = 0
    parent_id: str = ""
    children: list[WorkflowItem] = []


class PendingTaskItem(BaseModel):
    workflow_id: str
    workflow_type: str | None = None
    task_type: str
    title: str
    description: str
    started: str
    status: str = "pending"
    parent_id: str = ""
    assigned_user: str = ""
    assigned_group: str = ""


class WorkflowListItem(BaseModel):
    """A workflow record as shown in the DB-powered workflow list."""
    record_id: str
    workflow_id: str
    workflow_type: str
    workflow_key: str
    status: str
    started_by: str = ""
    created_at: str = ""
    closed_at: str = ""
    duration: str = ""
    parent_workflow_id: str = ""
    children: list[WorkflowListItem] = []


class PaginatedResult(BaseModel):
    items: list[WorkflowItem] | list[PendingTaskItem] | list[WorkflowListItem]
    has_next: bool


# ── Workflow detail ──

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


class WorkflowRun(BaseModel):
    """A single run entry in the workflow run history."""
    run_id: str
    status: str
    started: str
    duration: str


class TimelineEvent(BaseModel):
    event_id: int
    event_time: str
    label: str
    status: str  # "completed", "failed", "pending", "info"
    detail: str = ""
    link: str = ""
    duration: str = ""
    kind: str = ""
    input_data: str = ""
    assigned_user: str = ""
    assigned_group: str = ""


class TimelineStats(BaseModel):
    activity_time: str = ""
    wait_time: str = ""
    total_time: str = ""
    workflow_input: str = ""
    workflow_output: str = ""


class GraphNode(BaseModel):
    workflow_id: str
    workflow_type: str
    status: str
    label: str
    node_type: str = "workflow"
    is_current: bool = False
    started: str = ""
    duration: str = ""
    children: list[GraphNode] = []


# ── Task list (DB-powered) ──

class TaskListItem(BaseModel):
    """A task record as shown in the DB-powered task list."""
    task_id: str
    workflow_id: str
    task_type: str
    title: str
    description: str = ""
    status: str = "open"
    priority: str = "medium"
    assigned_user: str = ""
    assigned_group: str = ""
    created_by: str = ""
    completed_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    due_at: str = ""


class TaskFilters(BaseModel):
    """Query parameters for the task list page."""
    tab: str = "open"
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=10, le=100)
    task_type: str | None = None
    search: str | None = None
    assignment: str | None = None
    priority: str | None = None
    sort: str = "created_at"
    order: str = "desc"


# ── Workflow picker ──

class WorkflowPickerItem(BaseModel):
    """Workflow option shown in the start picker."""
    key: str
    label: str
    description: str
    input_label: str
    input_placeholder: str
    has_input_task: bool


# ── Pending task detail (with form for inline completion) ──

class PendingTaskDetail(BaseModel):
    """Pending task with attached form for inline completion on detail page."""
    model_config = {"arbitrary_types_allowed": True}

    workflow_id: str
    task_type: str
    title: str
    description: str
    assigned_user: str = ""
    assigned_group: str = ""
    started: str = ""
    form: Any = None
    errors: dict[str, list[str]] = {}


# ── API responses ──

class AssigneeOption(BaseModel):
    """A single user or group option for reassignment."""
    slug: str
    label: str


class AssigneesResponse(BaseModel):
    """Response from /api/assignees endpoint."""
    users: list[AssigneeOption]
    groups: list[AssigneeOption]


class ReassignResult(BaseModel):
    """Response from reassign endpoint."""
    ok: bool
    assigned_user: str = ""
    assigned_group: str = ""
    error: str = ""
