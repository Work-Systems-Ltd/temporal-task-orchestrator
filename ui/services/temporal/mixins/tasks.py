"""Mixin for pending task queries, signals, and assignment sanitization."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select

from core.models import TaskMeta
from core.workflows import WorkSysFlow

logger = logging.getLogger(__name__)


class TasksMixin:
    """Pending task operations — queries, completion signals, reassignment."""

    async def get_pending_task(self, workflow_id: str) -> TaskMeta | None:
        """Query a workflow for its current pending human task."""
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            raw = await handle.query(WorkSysFlow.get_pending_task)
            if not raw:
                return None
            meta = TaskMeta.model_validate_json(raw)
            return await self._sanitize_assignment(meta)
        except Exception as exc:
            logger.debug("Failed to get pending task for %s: %s", workflow_id, exc)
            return None

    async def signal_complete(self, workflow_id: str, data: str) -> None:
        """Signal a workflow that its human task has been completed."""
        handle = self._client.get_workflow_handle(workflow_id)
        await handle.signal(WorkSysFlow.complete_human_task, data)

    async def reassign_task(
        self, workflow_id: str, assigned_user: str = "", assigned_group: str = "",
    ) -> None:
        """Signal a workflow to update the assignment on its pending task."""
        handle = self._client.get_workflow_handle(workflow_id)
        payload = json.dumps({"assigned_user": assigned_user, "assigned_group": assigned_group})
        await handle.signal(WorkSysFlow.reassign_task, payload)

    @staticmethod
    async def _sanitize_assignment(meta: TaskMeta) -> TaskMeta:
        """Clear assigned_user/assigned_group if they reference non-existent entities."""
        if not meta.assigned_user and not meta.assigned_group:
            return meta

        from ui.auth.database import get_session_factory
        from ui.auth.models import Group, User, _slugify

        factory = get_session_factory()
        async with factory() as db:
            if meta.assigned_user:
                result = await db.execute(select(User.username))
                existing = {_slugify(row[0]) for row in result}
                if meta.assigned_user not in existing:
                    logger.warning(
                        "Task %r assigned to unknown user %r — clearing assignment",
                        meta.task_type, meta.assigned_user,
                    )
                    meta = meta.model_copy(update={"assigned_user": ""})

            if meta.assigned_group:
                result = await db.execute(select(Group.name))
                existing = {_slugify(row[0]) for row in result}
                if meta.assigned_group not in existing:
                    logger.warning(
                        "Task %r assigned to unknown group %r — clearing assignment",
                        meta.task_type, meta.assigned_group,
                    )
                    meta = meta.model_copy(update={"assigned_group": ""})

        return meta
