"""WorkflowTableView — workflow list page powered by GenericTableView."""
from __future__ import annotations

from fastapi import Request

from core.db import DbService, WorkflowRecord
from ui.helpers import duration, relative_time
from ui.models import WorkflowListItem

from .table_view import GenericTableView
from .types import Column, FilterDef, QueryField, SortOption, TabConfig


class WorkflowTableView(GenericTableView[WorkflowRecord, WorkflowListItem]):
    model_class = WorkflowRecord
    serializer_class = WorkflowListItem
    template = "workflows/list.html"
    url_prefix = "/workflows"
    page_title = "Workflows"
    route_name = "workflows_page"

    tabs = TabConfig(
        order=["running", "completed", "failed", "all"],
        labels={
            "running": "Running",
            "completed": "Completed",
            "failed": "Failed",
            "all": "All",
        },
        status_field="status",
        default_tab="running",
        status_groups={
            "running": ["starting", "running"],
            "failed": ["failed", "cancelled", "terminated", "timed_out"],
        },
    )

    columns = [
        Column(key="workflow_id", label="Workflow ID", sortable=True, render="workflow_id_cell"),
        Column(key="workflow_type", label="Type", css_class="hidden sm:table-cell"),
        Column(key="started_by", label="Started By", css_class="hidden sm:table-cell"),
        Column(key="started", label="Started", sortable=True),
        Column(key="closed", label="Stopped", css_class="hidden md:table-cell"),
        Column(key="duration", label="Duration", css_class="hidden md:table-cell"),
        Column(key="status", label="Status", render="status_badge_cell"),
    ]

    filters = [
        FilterDef(key="type", label="Type", field="workflow_type"),
    ]

    sort_options = [
        SortOption("created_at:desc", "Newest first"),
        SortOption("created_at:asc", "Oldest first"),
    ]

    query_fields = [
        QueryField("workflow_id", "Workflow ID", "string"),
        QueryField("workflow_type", "Type", "string"),
        QueryField(
            "status",
            "Status",
            "enum",
            enum_values=["starting", "running", "completed", "failed", "cancelled", "terminated", "timed_out"],
        ),
        QueryField("started_by", "Started By", "string"),
        QueryField("created_at", "Created", "date"),
    ]

    search_fields = ["workflow_id", "workflow_type", "workflow_key"]

    def convert_record(self, record: WorkflowRecord) -> WorkflowListItem:
        return WorkflowListItem(
            record_id=str(record.id),
            workflow_id=record.workflow_id,
            workflow_type=record.workflow_type,
            workflow_key=record.workflow_key,
            status=record.status if record.status != "starting" else "running",
            started=relative_time(record.created_at),
            closed=relative_time(record.closed_at),
            duration=duration(record.created_at, record.closed_at),
            started_by=record.started_by or "",
        )

    def get_hash_exclude_fields(self) -> set[str]:
        return {"started", "closed", "duration"}

    async def get_tab_counts(self, request: Request, db: DbService) -> dict[str, int]:
        return await db.count_workflows_by_status()

    async def get_filter_options(
        self, key: str, request: Request, db: DbService
    ) -> list[str]:
        if key == "type":
            from core.workflows import get_all_workflows
            return [wf.workflow_cls.__name__ for wf in get_all_workflows()]
        return []

    async def get_extra_context(self, request: Request, db: DbService) -> dict:
        """Provide backward-compatible context vars for the existing workflow template."""
        from core.workflows import get_all_workflows
        return {
            "tabs": self.tabs.order,
            "counts": await self.get_tab_counts(request, db),
            "wf_type": request.query_params.get("type", ""),
            "workflow_types": [wf.workflow_cls.__name__ for wf in get_all_workflows()],
        }
