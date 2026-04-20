"""Mixin for workflow record queries."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select

from core.db.models import TaskRecord, WorkflowRecord


RUNNING_STATUSES = {"starting", "running"}
CLOSED_STATUSES = {"completed", "failed", "cancelled", "terminated", "timed_out"}
ALL_STATUSES = RUNNING_STATUSES | CLOSED_STATUSES


class WorkflowsMixin:
    """Workflow record queries and mutations."""

    async def get_workflow_by_workflow_id(self, workflow_id: str) -> WorkflowRecord | None:
        """Get a workflow record by its Temporal workflow ID."""
        async with self._session() as db:
            stmt = select(WorkflowRecord).where(WorkflowRecord.workflow_id == workflow_id)
            return (await db.execute(stmt)).scalar_one_or_none()

    async def get_workflow_by_record_id(self, record_id: uuid.UUID) -> WorkflowRecord | None:
        """Get a workflow record by its internal UUID primary key."""
        async with self._session() as db:
            stmt = select(WorkflowRecord).where(WorkflowRecord.id == record_id)
            return (await db.execute(stmt)).scalar_one_or_none()

    async def list_workflows(
        self,
        *,
        status: str | None = None,
        workflow_type: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[WorkflowRecord], int]:
        """List workflows with filtering, pagination, and sorting.

        Returns:
            Tuple of (workflow records, total count).
        """
        async with self._session() as db:
            stmt = select(WorkflowRecord)
            count_stmt = select(func.count(WorkflowRecord.id))

            # Status filter
            if status and status != "all":
                if status == "running":
                    stmt = stmt.where(WorkflowRecord.status.in_(list(RUNNING_STATUSES)))
                    count_stmt = count_stmt.where(WorkflowRecord.status.in_(list(RUNNING_STATUSES)))
                else:
                    stmt = stmt.where(WorkflowRecord.status == status)
                    count_stmt = count_stmt.where(WorkflowRecord.status == status)

            # Workflow type filter
            if workflow_type:
                stmt = stmt.where(WorkflowRecord.workflow_type == workflow_type)
                count_stmt = count_stmt.where(WorkflowRecord.workflow_type == workflow_type)

            # Search (workflow_id, workflow_type, workflow_key)
            if search:
                like = f"%{search}%"
                search_filter = or_(
                    WorkflowRecord.workflow_id.ilike(like),
                    WorkflowRecord.workflow_type.ilike(like),
                    WorkflowRecord.workflow_key.ilike(like),
                )
                stmt = stmt.where(search_filter)
                count_stmt = count_stmt.where(search_filter)

            # Get total count
            total = (await db.execute(count_stmt)).scalar() or 0

            # Sorting
            sort_col = getattr(WorkflowRecord, sort, WorkflowRecord.created_at)
            stmt = stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

            # Pagination
            offset = (page - 1) * per_page
            stmt = stmt.offset(offset).limit(per_page)

            rows = list((await db.execute(stmt)).scalars().all())
            return rows, total

    async def count_workflows_by_status(self) -> dict[str, int]:
        """Count workflows grouped by status."""
        async with self._session() as db:
            stmt = select(
                WorkflowRecord.status, func.count(WorkflowRecord.id)
            ).group_by(WorkflowRecord.status)
            rows = (await db.execute(stmt)).all()

            counts: dict[str, int] = {
                "running": 0,
                "completed": 0,
                "failed": 0,
            }
            for status_val, count in rows:
                if status_val in RUNNING_STATUSES:
                    counts["running"] = counts.get("running", 0) + count
                elif status_val in counts:
                    counts[status_val] = count
                # Other statuses like cancelled/terminated/timed_out grouped into failed
                elif status_val in CLOSED_STATUSES:
                    counts["failed"] = counts.get("failed", 0) + count

            counts["all"] = sum(counts.values())
            return counts

    async def get_workflow_children(self, workflow_id: str) -> list[WorkflowRecord]:
        """Get direct child workflows of a given workflow."""
        async with self._session() as db:
            # First get the parent's record ID
            parent = await self.get_workflow_by_workflow_id(workflow_id)
            if not parent:
                return []
            stmt = (
                select(WorkflowRecord)
                .where(WorkflowRecord.parent_id == parent.id)
                .order_by(WorkflowRecord.created_at)
            )
            return list((await db.execute(stmt)).scalars().all())

    async def create_workflow_placeholder(
        self,
        *,
        workflow_id: str,
        workflow_key: str,
        workflow_type: str,
        started_by: str = "",
        input_data: dict | None = None,
    ) -> WorkflowRecord:
        """Create a placeholder workflow record with status='starting'.

        Called by the router before starting the Temporal workflow so we can
        capture started_by.  The workflow's activity will later update this
        record to status='running'.
        """
        async with self._session() as db:
            record = WorkflowRecord(
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                workflow_key=workflow_key,
                status="starting",
                started_by=started_by or None,
                input_data=input_data,
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return record

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow record and all associated tasks from the database.

        Deletes tasks first (which cascade-deletes comments and activity logs),
        then nullifies parent references on child workflows, then deletes the
        workflow record itself. Does NOT affect the Temporal execution.
        """
        async with self._session() as db:
            record = (
                await db.execute(
                    select(WorkflowRecord).where(WorkflowRecord.workflow_id == workflow_id)
                )
            ).scalar_one_or_none()
            if not record:
                return False

            # Delete all tasks linked to this workflow (comments/activity cascade via ORM)
            tasks = (
                await db.execute(
                    select(TaskRecord).where(TaskRecord.workflow_id == workflow_id)
                )
            ).scalars().all()
            for task in tasks:
                await db.delete(task)

            # Nullify parent_id on child workflows so they aren't orphan-blocked
            children = (
                await db.execute(
                    select(WorkflowRecord).where(WorkflowRecord.parent_id == record.id)
                )
            ).scalars().all()
            for child in children:
                child.parent_id = None

            await db.delete(record)
            await db.commit()
            return True

    async def get_distinct_workflow_types(self) -> list[str]:
        """Return all distinct workflow_type values."""
        async with self._session() as db:
            stmt = (
                select(WorkflowRecord.workflow_type)
                .distinct()
                .order_by(WorkflowRecord.workflow_type)
            )
            return list((await db.execute(stmt)).scalars().all())
