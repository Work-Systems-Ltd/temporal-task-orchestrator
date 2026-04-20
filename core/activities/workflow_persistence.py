"""Temporal activities for persisting workflow records to the database.

These activities are called by WorkSysFlow during workflow lifecycle events
(start, completion, failure) so that the DB stays in sync with Temporal
workflow state.  Because they are Temporal activities they participate in
the retry / failure model automatically.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio import activity


class CreateWorkflowInput(BaseModel):
    """Input for the create_workflow_record activity."""
    workflow_id: str
    run_id: str = ""
    workflow_type: str
    workflow_key: str
    parent_workflow_id: str = ""
    input_data: str = ""  # JSON string
    task_queue: str = ""


class CompleteWorkflowInput(BaseModel):
    """Input for the complete_workflow_record activity."""
    workflow_id: str
    output_data: str = ""  # JSON string


class FailWorkflowInput(BaseModel):
    """Input for the fail_workflow_record activity."""
    workflow_id: str
    error_message: str = ""


@dataclass
class WorkflowPersistenceActivities:
    """Activity class that holds a DB session factory.

    Instantiated in the worker with the session factory, then all
    methods are registered as Temporal activities.
    """
    session_factory: async_sessionmaker[AsyncSession]

    @activity.defn
    async def create_workflow_record(self, raw_input: str) -> str:
        """Upsert a workflow record with status='running'.

        If a placeholder record exists (status='starting', created by the
        router), update it.  Otherwise create a new record (e.g. for child
        workflows started directly by Temporal).
        """
        from ui.auth.models import TaskRecord, WorkflowRecord

        data = CreateWorkflowInput.model_validate_json(raw_input)

        # Parse input_data JSON
        input_dict = None
        if data.input_data:
            try:
                input_dict = json.loads(data.input_data)
            except (json.JSONDecodeError, TypeError):
                input_dict = {"raw": data.input_data}

        now = datetime.now(timezone.utc)

        async with self.session_factory() as db:
            # Resolve parent
            parent_uuid = None
            if data.parent_workflow_id:
                stmt = select(WorkflowRecord.id).where(
                    WorkflowRecord.workflow_id == data.parent_workflow_id
                )
                parent_uuid = (await db.execute(stmt)).scalar_one_or_none()

            # Check for existing placeholder
            stmt = select(WorkflowRecord).where(
                WorkflowRecord.workflow_id == data.workflow_id
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if existing:
                existing.run_id = data.run_id or None
                existing.workflow_type = data.workflow_type
                existing.workflow_key = data.workflow_key
                existing.status = "running"
                existing.parent_id = parent_uuid
                existing.updated_at = now
                existing.task_queue = data.task_queue or None
                if input_dict and not existing.input_data:
                    existing.input_data = input_dict
                record_id = existing.id
            else:
                record = WorkflowRecord(
                    id=uuid.uuid4(),
                    workflow_id=data.workflow_id,
                    run_id=data.run_id or None,
                    workflow_type=data.workflow_type,
                    workflow_key=data.workflow_key,
                    status="running",
                    parent_id=parent_uuid,
                    input_data=input_dict,
                    task_queue=data.task_queue or None,
                )
                db.add(record)
                record_id = record.id

            # Backfill workflow_record_id on any tasks with matching workflow_id
            await db.execute(
                update(TaskRecord)
                .where(TaskRecord.workflow_id == data.workflow_id)
                .where(TaskRecord.workflow_record_id.is_(None))
                .values(workflow_record_id=record_id)
            )

            await db.commit()

        activity.logger.info(
            "Created/updated workflow record for %s (status=running)", data.workflow_id
        )
        return str(record_id)

    @activity.defn
    async def complete_workflow_record(self, raw_input: str) -> None:
        """Mark a workflow as completed, storing optional output data."""
        from ui.auth.models import WorkflowRecord

        data = CompleteWorkflowInput.model_validate_json(raw_input)
        now = datetime.now(timezone.utc)

        output_dict = None
        if data.output_data:
            try:
                output_dict = json.loads(data.output_data)
            except (json.JSONDecodeError, TypeError):
                output_dict = {"raw": data.output_data}

        async with self.session_factory() as db:
            stmt = (
                update(WorkflowRecord)
                .where(WorkflowRecord.workflow_id == data.workflow_id)
                .values(
                    status="completed",
                    closed_at=now,
                    updated_at=now,
                    output_data=output_dict,
                )
            )
            await db.execute(stmt)
            await db.commit()

        activity.logger.info("Completed workflow record %s", data.workflow_id)

    @activity.defn
    async def fail_workflow_record(self, raw_input: str) -> None:
        """Mark a workflow as failed, storing the error message."""
        from ui.auth.models import WorkflowRecord

        data = FailWorkflowInput.model_validate_json(raw_input)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as db:
            stmt = (
                update(WorkflowRecord)
                .where(WorkflowRecord.workflow_id == data.workflow_id)
                .values(
                    status="failed",
                    closed_at=now,
                    updated_at=now,
                    error_message=data.error_message or None,
                )
            )
            await db.execute(stmt)
            await db.commit()

        activity.logger.info("Failed workflow record %s", data.workflow_id)
