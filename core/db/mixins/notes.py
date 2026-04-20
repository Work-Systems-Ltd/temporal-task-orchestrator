"""Mixin for note queries."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from core.db.models import Note, WorkflowRecord


class NotesMixin:
    """Note CRUD operations."""

    async def get_notes_for_task(self, task_id: str) -> list[Note]:
        """Get all notes for a task, ordered by creation time."""
        async with self._session() as db:
            stmt = (
                select(Note)
                .where(Note.task_id == uuid.UUID(task_id))
                .order_by(Note.created_at)
            )
            return list((await db.execute(stmt)).scalars().all())

    async def get_notes_for_workflow(self, workflow_id: str) -> list[Note]:
        """Get all notes for a workflow (by Temporal workflow ID string)."""
        async with self._session() as db:
            # Resolve workflow_id string to record UUID
            wf = (
                await db.execute(
                    select(WorkflowRecord.id).where(
                        WorkflowRecord.workflow_id == workflow_id
                    )
                )
            ).scalar_one_or_none()
            if not wf:
                return []
            stmt = (
                select(Note)
                .where(Note.workflow_id == wf)
                .order_by(Note.created_at)
            )
            return list((await db.execute(stmt)).scalars().all())

    async def add_note(
        self,
        *,
        author: str,
        content: str,
        task_id: str | None = None,
        workflow_id: str | None = None,
    ) -> Note:
        """Create a note on a task or workflow.

        For workflow notes, pass the Temporal workflow_id string — the record
        UUID is resolved automatically.
        """
        async with self._session() as db:
            wf_record_id: uuid.UUID | None = None
            if workflow_id:
                wf_record_id = (
                    await db.execute(
                        select(WorkflowRecord.id).where(
                            WorkflowRecord.workflow_id == workflow_id
                        )
                    )
                ).scalar_one_or_none()
                if not wf_record_id:
                    raise ValueError(f"Workflow {workflow_id} not found")

            note = Note(
                task_id=uuid.UUID(task_id) if task_id else None,
                workflow_id=wf_record_id,
                author=author,
                content=content,
            )
            db.add(note)
            await db.commit()
            await db.refresh(note)
            return note

    async def update_note(self, note_id: str, content: str) -> Note | None:
        """Update note content. Returns updated note or None if not found."""
        async with self._session() as db:
            note = (
                await db.execute(
                    select(Note).where(Note.id == uuid.UUID(note_id))
                )
            ).scalar_one_or_none()
            if not note:
                return None
            note.content = content
            note.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(note)
            return note

    async def delete_note(self, note_id: str) -> bool:
        """Delete a note. Returns True if deleted, False if not found."""
        async with self._session() as db:
            note = (
                await db.execute(
                    select(Note).where(Note.id == uuid.UUID(note_id))
                )
            ).scalar_one_or_none()
            if not note:
                return False
            await db.delete(note)
            await db.commit()
            return True

    async def get_note_by_id(self, note_id: str) -> Note | None:
        """Get a single note by ID."""
        async with self._session() as db:
            return (
                await db.execute(
                    select(Note).where(Note.id == uuid.UUID(note_id))
                )
            ).scalar_one_or_none()
