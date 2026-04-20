"""TaskTableView — task list page powered by GenericTableView."""
from __future__ import annotations

from fastapi import Request

from core.db import DbService, TaskRecord
from ui.models import TaskListItem

from .table_view import GenericTableView
from .types import Column, FilterDef, QueryField, SortOption, TabConfig


def _format_dt(dt) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


class TaskTableView(GenericTableView[TaskRecord, TaskListItem]):
    model_class = TaskRecord
    serializer_class = TaskListItem
    template = "tasks/list.html"
    url_prefix = "/tasks"
    page_title = "Tasks"
    route_name = "tasks_page"

    tabs = TabConfig(
        order=["open", "in_progress", "on_hold", "completed", "cancelled", "all"],
        labels={
            "open": "Open",
            "in_progress": "In Progress",
            "on_hold": "On Hold",
            "completed": "Completed",
            "cancelled": "Cancelled",
            "all": "All",
        },
        status_field="status",
        default_tab="open",
    )

    columns = [
        Column(key="title", label="Task", sortable=True, render="task_title_cell"),
        Column(key="task_type", label="Type", css_class="hidden sm:table-cell", sortable=True, sort_field="task_type"),
        Column(key="assigned_user", label="User", css_class="hidden sm:table-cell"),
        Column(key="assigned_group", label="Group", css_class="hidden sm:table-cell"),
        Column(
            key="workflow_id",
            label="Workflow",
            css_class="hidden md:table-cell",
            render="workflow_link_cell",
        ),
        Column(key="created_at", label="Created", sortable=True),
    ]

    filters = [
        FilterDef(key="type", label="Type", field="task_type"),
        FilterDef(key="priority", label="Priority", field="priority"),
        FilterDef(key="assignment", label="Assignment"),
    ]

    sort_options = [
        SortOption("created_at:desc", "Newest first"),
        SortOption("created_at:asc", "Oldest first"),
        SortOption("priority:asc", "Priority (high to low)"),
        SortOption("updated_at:desc", "Recently updated"),
    ]

    query_fields = [
        QueryField("title", "Title", "string"),
        QueryField("task_type", "Type", "string"),
        QueryField(
            "priority",
            "Priority",
            "enum",
            enum_values=["critical", "high", "medium", "low"],
        ),
        QueryField("assigned_user", "Assigned User", "string"),
        QueryField("assigned_group", "Assigned Group", "string"),
        QueryField(
            "status",
            "Status",
            "enum",
            enum_values=["open", "in_progress", "on_hold", "completed", "cancelled"],
        ),
        QueryField("created_at", "Created", "date"),
        QueryField("due_at", "Due Date", "date"),
    ]

    search_fields = ["title", "description", "workflow_id"]

    def convert_record(self, record: TaskRecord) -> TaskListItem:
        return TaskListItem(
            task_id=str(record.id),
            workflow_id=record.workflow_id,
            task_type=record.task_type,
            title=record.title,
            description=record.description or "",
            status=record.status,
            priority=record.priority,
            assigned_user=record.assigned_user or "",
            assigned_group=record.assigned_group or "",
            created_by=record.created_by or "",
            completed_by=record.completed_by or "",
            created_at=_format_dt(record.created_at),
            updated_at=_format_dt(record.updated_at),
            completed_at=_format_dt(record.completed_at),
            due_at=_format_dt(record.due_at),
        )

    async def get_access_filter(self, request: Request, db: DbService) -> list | None:
        user = getattr(request.state, "user", None)
        if not user or user.is_admin:
            return None
        conditions = [
            (TaskRecord.assigned_user.is_(None))
            & (TaskRecord.assigned_group.is_(None)),
        ]
        if user.slug:
            conditions.append(TaskRecord.assigned_user == user.slug)
        for gs in user.group_slugs:
            conditions.append(TaskRecord.assigned_group == gs)
        return conditions

    async def get_tab_counts(self, request: Request, db: DbService) -> dict[str, int]:
        user = getattr(request.state, "user", None)
        return await db.count_tasks_by_status(
            user_slug=user.slug if user else "",
            user_group_slugs=user.group_slugs if user else [],
            is_admin=user.is_admin if user else False,
        )

    async def get_filter_options(
        self, key: str, request: Request, db: DbService
    ) -> list[str]:
        if key == "type":
            return await db.get_distinct_task_types()
        if key == "priority":
            return ["critical", "high", "medium", "low"]
        if key == "assignment":
            return ["mine", "my_groups", "unassigned"]
        return []

    def get_simple_filter_conditions(
        self, request: Request, simple_filters: dict[str, str]
    ) -> list:
        """Handle task-specific filters like assignment which need user context."""
        conditions = []
        user = getattr(request.state, "user", None)

        for fdef in self.filters:
            value = simple_filters.get(fdef.key)
            if not value:
                continue

            if fdef.key == "assignment":
                # Special handling: assignment is not a direct column match
                if value == "mine" and user:
                    conditions.append(TaskRecord.assigned_user == user.slug)
                elif value == "my_groups" and user:
                    if user.group_slugs:
                        conditions.append(
                            TaskRecord.assigned_group.in_(user.group_slugs)
                        )
                elif value == "unassigned":
                    conditions.append(TaskRecord.assigned_user.is_(None))
                    conditions.append(TaskRecord.assigned_group.is_(None))
            else:
                col_name = fdef.field or fdef.key
                col = getattr(self.model_class, col_name, None)
                if col is not None:
                    conditions.append(col == value)

        return conditions
