"""Mixin for task record queries."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select, update

from ui.auth.models import TaskActivityLog, TaskComment, TaskRecord


# Valid status transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "on_hold", "cancelled"},
    "in_progress": {"on_hold", "completed", "cancelled"},
    "on_hold": {"open", "in_progress", "cancelled"},
}

ACTIVE_STATUSES = {"open", "in_progress", "on_hold"}
CLOSED_STATUSES = {"completed", "cancelled"}
ALL_STATUSES = ACTIVE_STATUSES | CLOSED_STATUSES


class TasksMixin:
    """Task record queries and mutations."""

    async def get_task_by_id(self, task_id: str) -> TaskRecord | None:
        async with self._session() as db:
            stmt = select(TaskRecord).where(TaskRecord.id == uuid.UUID(task_id))
            return (await db.execute(stmt)).scalar_one_or_none()

    async def get_task_by_workflow_id(self, workflow_id: str) -> TaskRecord | None:
        """Get the most recent task for a workflow."""
        async with self._session() as db:
            stmt = (
                select(TaskRecord)
                .where(TaskRecord.workflow_id == workflow_id)
                .order_by(TaskRecord.created_at.desc())
                .limit(1)
            )
            return (await db.execute(stmt)).scalar_one_or_none()

    async def get_tasks_by_workflow_id(self, workflow_id: str) -> list[TaskRecord]:
        """Get all tasks for a workflow, ordered by creation time."""
        async with self._session() as db:
            stmt = (
                select(TaskRecord)
                .where(TaskRecord.workflow_id == workflow_id)
                .order_by(TaskRecord.created_at)
            )
            return list((await db.execute(stmt)).scalars().all())

    async def list_tasks(
        self,
        *,
        status: str | None = None,
        task_type: str | None = None,
        assigned_user: str | None = None,
        assigned_group: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        # Access control
        user_slug: str = "",
        user_group_slugs: list[str] | None = None,
        is_admin: bool = False,
        # Pagination & sorting
        page: int = 1,
        per_page: int = 20,
        sort: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[TaskRecord], int]:
        """List tasks with filtering, access control, pagination, and sorting.

        Returns:
            Tuple of (task records, total count).
        """
        async with self._session() as db:
            stmt = select(TaskRecord)
            count_stmt = select(func.count(TaskRecord.id))

            # Status filter
            if status and status != "all":
                stmt = stmt.where(TaskRecord.status == status)
                count_stmt = count_stmt.where(TaskRecord.status == status)

            # Task type filter
            if task_type:
                stmt = stmt.where(TaskRecord.task_type == task_type)
                count_stmt = count_stmt.where(TaskRecord.task_type == task_type)

            # Priority filter
            if priority:
                stmt = stmt.where(TaskRecord.priority == priority)
                count_stmt = count_stmt.where(TaskRecord.priority == priority)

            # Assignment filter
            if assigned_user:
                stmt = stmt.where(TaskRecord.assigned_user == assigned_user)
                count_stmt = count_stmt.where(TaskRecord.assigned_user == assigned_user)
            if assigned_group:
                stmt = stmt.where(TaskRecord.assigned_group == assigned_group)
                count_stmt = count_stmt.where(TaskRecord.assigned_group == assigned_group)

            # Search (title, description, workflow_id)
            if search:
                like = f"%{search}%"
                search_filter = or_(
                    TaskRecord.title.ilike(like),
                    TaskRecord.description.ilike(like),
                    TaskRecord.workflow_id.ilike(like),
                )
                stmt = stmt.where(search_filter)
                count_stmt = count_stmt.where(search_filter)

            # Access control — non-admins see only tasks assigned to them,
            # their groups, or unassigned tasks
            if not is_admin:
                access_conditions = [
                    # Unassigned tasks
                    (TaskRecord.assigned_user.is_(None)) & (TaskRecord.assigned_group.is_(None)),
                ]
                if user_slug:
                    access_conditions.append(TaskRecord.assigned_user == user_slug)
                for gs in (user_group_slugs or []):
                    access_conditions.append(TaskRecord.assigned_group == gs)

                stmt = stmt.where(or_(*access_conditions))
                count_stmt = count_stmt.where(or_(*access_conditions))

            # Get total count
            total = (await db.execute(count_stmt)).scalar() or 0

            # Sorting
            sort_col = getattr(TaskRecord, sort, TaskRecord.created_at)
            stmt = stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

            # Pagination
            offset = (page - 1) * per_page
            stmt = stmt.offset(offset).limit(per_page)

            rows = list((await db.execute(stmt)).scalars().all())
            return rows, total

    async def count_tasks_by_status(
        self,
        *,
        user_slug: str = "",
        user_group_slugs: list[str] | None = None,
        is_admin: bool = False,
    ) -> dict[str, int]:
        """Count tasks grouped by status, respecting access control."""
        async with self._session() as db:
            stmt = select(TaskRecord.status, func.count(TaskRecord.id)).group_by(TaskRecord.status)

            if not is_admin:
                access_conditions = [
                    (TaskRecord.assigned_user.is_(None)) & (TaskRecord.assigned_group.is_(None)),
                ]
                if user_slug:
                    access_conditions.append(TaskRecord.assigned_user == user_slug)
                for gs in (user_group_slugs or []):
                    access_conditions.append(TaskRecord.assigned_group == gs)
                stmt = stmt.where(or_(*access_conditions))

            rows = (await db.execute(stmt)).all()
            counts = {s: 0 for s in ALL_STATUSES}
            for status_val, count in rows:
                counts[status_val] = count
            counts["all"] = sum(counts.values())
            return counts

    async def update_task_status(
        self, task_id: str, new_status: str, actor: str = ""
    ) -> TaskRecord | None:
        """Transition a task to a new status if valid. Returns updated record or None."""
        async with self._session() as db:
            record = (
                await db.execute(
                    select(TaskRecord).where(TaskRecord.id == uuid.UUID(task_id))
                )
            ).scalar_one_or_none()

            if not record:
                return None

            allowed = VALID_TRANSITIONS.get(record.status, set())
            if new_status not in allowed:
                return None

            now = datetime.now(timezone.utc)
            record.status = new_status
            record.updated_at = now
            if new_status in CLOSED_STATUSES:
                record.completed_at = now
                if actor:
                    record.completed_by = actor

            await db.commit()
            await db.refresh(record)
            return record

    async def update_task_assignment(
        self,
        task_id: str,
        assigned_user: str | None = None,
        assigned_group: str | None = None,
    ) -> TaskRecord | None:
        """Update task assignment in the database."""
        async with self._session() as db:
            record = (
                await db.execute(
                    select(TaskRecord).where(TaskRecord.id == uuid.UUID(task_id))
                )
            ).scalar_one_or_none()

            if not record:
                return None

            now = datetime.now(timezone.utc)
            if assigned_user is not None:
                record.assigned_user = assigned_user or None
            if assigned_group is not None:
                record.assigned_group = assigned_group or None
            record.updated_at = now

            await db.commit()
            await db.refresh(record)
            return record

    async def get_distinct_task_types(self) -> list[str]:
        """Return all distinct task_type values in the tasks table."""
        async with self._session() as db:
            stmt = select(TaskRecord.task_type).distinct().order_by(TaskRecord.task_type)
            return list((await db.execute(stmt)).scalars().all())

    # ── Comments ──

    async def get_task_comments(self, task_id: str) -> list[TaskComment]:
        """Get all comments for a task, ordered by creation time."""
        async with self._session() as db:
            stmt = (
                select(TaskComment)
                .where(TaskComment.task_id == uuid.UUID(task_id))
                .order_by(TaskComment.created_at)
            )
            return list((await db.execute(stmt)).scalars().all())

    async def add_task_comment(
        self, task_id: str, author: str, content: str, is_internal: bool = False
    ) -> TaskComment:
        """Add a comment to a task."""
        async with self._session() as db:
            comment = TaskComment(
                task_id=uuid.UUID(task_id),
                author=author,
                content=content,
                is_internal=is_internal,
            )
            db.add(comment)

            # Also log the activity
            db.add(TaskActivityLog(
                task_id=uuid.UUID(task_id),
                action="commented",
                actor=author,
                new_value=content[:500],
            ))

            await db.commit()
            await db.refresh(comment)
            return comment

    # ── Activity Log ──

    async def get_task_activity(self, task_id: str) -> list[TaskActivityLog]:
        """Get the activity log for a task, newest first."""
        async with self._session() as db:
            stmt = (
                select(TaskActivityLog)
                .where(TaskActivityLog.task_id == uuid.UUID(task_id))
                .order_by(TaskActivityLog.created_at.desc())
            )
            return list((await db.execute(stmt)).scalars().all())

    async def log_task_activity(
        self,
        task_id: str,
        action: str,
        actor: str = "",
        old_value: str = "",
        new_value: str = "",
        detail: dict | None = None,
    ) -> None:
        """Write an entry to the task activity log."""
        async with self._session() as db:
            db.add(TaskActivityLog(
                task_id=uuid.UUID(task_id),
                action=action,
                actor=actor or None,
                old_value=old_value or None,
                new_value=new_value or None,
                detail=detail,
            ))
            await db.commit()

    # ── Dashboard Metrics ──

    async def get_task_summary_counts(self) -> dict[str, int]:
        """Aggregate task counts for dashboard summary cards."""
        async with self._session() as db:
            # Count by status
            stmt = select(TaskRecord.status, func.count(TaskRecord.id)).group_by(TaskRecord.status)
            rows = (await db.execute(stmt)).all()
            counts = {s: 0 for s in ALL_STATUSES}
            for status_val, count in rows:
                counts[status_val] = count
            counts["total"] = sum(counts.values())
            counts["active"] = counts["open"] + counts["in_progress"] + counts["on_hold"]
            return counts

    async def get_overdue_count(self) -> int:
        """Count tasks that are past their due date and still active."""
        async with self._session() as db:
            now = datetime.now(timezone.utc)
            stmt = select(func.count(TaskRecord.id)).where(
                TaskRecord.due_at < now,
                TaskRecord.status.in_(list(ACTIVE_STATUSES)),
            )
            return (await db.execute(stmt)).scalar() or 0

    async def get_completed_count_since(self, since: datetime) -> int:
        """Count tasks completed since a given time."""
        async with self._session() as db:
            stmt = select(func.count(TaskRecord.id)).where(
                TaskRecord.completed_at >= since,
                TaskRecord.status == "completed",
            )
            return (await db.execute(stmt)).scalar() or 0
