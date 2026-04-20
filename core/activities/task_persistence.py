"""Temporal activities for persisting task records to the database.

These activities are called by WorkSysFlow during task lifecycle events
(creation, completion, reassignment, cancellation) so that the DB stays
in sync with Temporal workflow state.  Because they are Temporal activities
they participate in the retry / failure model automatically.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio import activity


class CreateTaskInput(BaseModel):
    """Input for the create_task_record activity."""
    task_id: str
    workflow_id: str
    run_id: str = ""
    task_type: str
    title: str
    description: str = ""
    priority: str = "medium"
    assigned_user: str = ""
    assigned_group: str = ""
    created_by: str = ""


class CompleteTaskInput(BaseModel):
    """Input for the complete_task_record activity."""
    task_id: str
    form_data: dict | None = None
    completed_by: str = ""


class UpdateTaskInput(BaseModel):
    """Input for the update_task_record activity."""
    task_id: str
    assigned_user: str | None = None
    assigned_group: str | None = None
    status: str | None = None
    priority: str | None = None


class CancelTaskInput(BaseModel):
    """Input for the cancel_task_record activity."""
    task_id: str


@dataclass
class TaskPersistenceActivities:
    """Activity class that holds a DB session factory.

    Instantiated in the worker with the session factory, then all
    methods are registered as Temporal activities.
    """
    session_factory: async_sessionmaker[AsyncSession]

    @activity.defn
    async def create_task_record(self, raw_input: str) -> str:
        """Insert a new task record with status='open'. Returns the task_id."""
        from core.db.models import TaskRecord, WorkflowRecord

        data = CreateTaskInput.model_validate_json(raw_input)

        async with self.session_factory() as db:
            # Try to link to workflow record if it exists
            workflow_record_id = None
            if data.workflow_id:
                try:
                    stmt = select(WorkflowRecord.id).where(
                        WorkflowRecord.workflow_id == data.workflow_id
                    )
                    workflow_record_id = (await db.execute(stmt)).scalar_one_or_none()
                except Exception:
                    pass  # workflow record may not exist yet

            record = TaskRecord(
                id=uuid.UUID(data.task_id),
                workflow_id=data.workflow_id,
                run_id=data.run_id or None,
                workflow_record_id=workflow_record_id,
                task_type=data.task_type,
                title=data.title,
                description=data.description or None,
                status="open",
                priority=data.priority,
                assigned_user=data.assigned_user or None,
                assigned_group=data.assigned_group or None,
                created_by=data.created_by or None,
            )

            db.add(record)
            await db.commit()

        activity.logger.info("Created task record %s for workflow %s", data.task_id, data.workflow_id)
        return data.task_id

    @activity.defn
    async def complete_task_record(self, raw_input: str) -> None:
        """Mark a task as completed, storing the submitted form data."""
        from core.db.models import TaskRecord

        data = CompleteTaskInput.model_validate_json(raw_input)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as db:
            stmt = (
                update(TaskRecord)
                .where(TaskRecord.id == uuid.UUID(data.task_id))
                .values(
                    status="completed",
                    completed_by=data.completed_by or None,
                    completed_at=now,
                    updated_at=now,
                    form_data=data.form_data,
                )
            )
            await db.execute(stmt)
            await db.commit()

        activity.logger.info("Completed task record %s", data.task_id)

    @activity.defn
    async def update_task_record(self, raw_input: str) -> None:
        """Update mutable fields on a task record (reassignment, status, priority)."""
        from core.db.models import TaskRecord

        data = UpdateTaskInput.model_validate_json(raw_input)
        now = datetime.now(timezone.utc)

        values: dict = {"updated_at": now}
        if data.assigned_user is not None:
            values["assigned_user"] = data.assigned_user or None
        if data.assigned_group is not None:
            values["assigned_group"] = data.assigned_group or None
        if data.status is not None:
            values["status"] = data.status
            if data.status in ("completed", "cancelled"):
                values["completed_at"] = now
        if data.priority is not None:
            values["priority"] = data.priority

        async with self.session_factory() as db:
            stmt = (
                update(TaskRecord)
                .where(TaskRecord.id == uuid.UUID(data.task_id))
                .values(**values)
            )
            await db.execute(stmt)
            await db.commit()

        activity.logger.info("Updated task record %s: %s", data.task_id, list(values.keys()))

    @activity.defn
    async def cancel_task_record(self, raw_input: str) -> None:
        """Mark a task as cancelled."""
        from core.db.models import TaskRecord

        data = CancelTaskInput.model_validate_json(raw_input)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as db:
            stmt = (
                update(TaskRecord)
                .where(TaskRecord.id == uuid.UUID(data.task_id))
                .values(
                    status="cancelled",
                    completed_at=now,
                    updated_at=now,
                )
            )
            await db.execute(stmt)
            await db.commit()

        activity.logger.info("Cancelled task record %s", data.task_id)
