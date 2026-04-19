from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Type

from temporalio import workflow

from core.models import TaskMeta
from core.tasks.base import HumanTask


class WorkSysFlow:
    """Base class for workflows that pause for human input.

    Subclasses must be decorated with @workflow.defn and must define
    a @workflow.run method. They inherit the signal, query, and
    wait helpers from this class.
    """

    def __init__(self) -> None:
        self._human_task_complete: bool = False
        self._human_task_data: dict[str, Any] | None = None
        self._pending_task: TaskMeta | None = None

    @workflow.signal
    async def complete_human_task(self, data: str) -> None:
        self._human_task_data = json.loads(data)
        self._human_task_complete = True

    @workflow.signal
    async def reassign_task(self, data: str) -> None:
        """Update the assignment on the current pending task."""
        if self._pending_task:
            payload = json.loads(data)
            self._pending_task = self._pending_task.model_copy(update=payload)

    @workflow.query
    def get_pending_task(self) -> str:
        if self._pending_task:
            return self._pending_task.model_dump_json()
        return ""

    async def _wait_for_signal(self, task_meta: TaskMeta) -> dict[str, Any]:
        """Internal: set pending task and block until the human signal arrives."""
        self._pending_task = task_meta
        await workflow.wait_condition(lambda: self._human_task_complete)
        self._pending_task = None
        self._human_task_complete = False
        assert self._human_task_data is not None
        data = self._human_task_data
        self._human_task_data = None
        return data

    async def wait_for_task(
        self,
        task: Type[HumanTask],
        *,
        title: str,
        description: str,
        assigned_user: str = "",
        assigned_group: str = "",
    ) -> dict[str, Any]:
        """Block until a human completes the given task type.

        Args:
            task: The HumanTask class (used for type-safe task_type resolution).
            title: Human-readable task title shown in the UI.
            description: Task description shown in the UI.
            assigned_user: Optional user slug to assign the task to.
            assigned_group: Optional group slug to assign the task to.

        Returns:
            The parsed human task data dict.
        """
        task_meta = TaskMeta(
            task_type=task.task_type,
            title=title,
            description=description,
            assigned_user=assigned_user,
            assigned_group=assigned_group,
        )
        return await self._wait_for_signal(task_meta)

    async def create_human_task(
        self,
        activity,
        *args,
        task: Type[HumanTask],
        title: str,
        description: str,
        assigned_user: str = "",
        assigned_group: str = "",
        start_to_close_timeout: timedelta = timedelta(seconds=10),
    ) -> dict[str, Any]:
        """Execute an activity then block until a human task is completed.

        Combines ``workflow.execute_activity`` + ``wait_for_task``
        into a single call.
        """
        await workflow.execute_activity(
            activity,
            args=list(args),
            start_to_close_timeout=start_to_close_timeout,
        )
        return await self.wait_for_task(
            task,
            title=title,
            description=description,
            assigned_user=assigned_user,
            assigned_group=assigned_group,
        )

    async def create_system_task(
        self,
        activity,
        *args,
        start_to_close_timeout: timedelta = timedelta(seconds=10),
    ) -> Any:
        """Execute an activity as a system task (no human input required).

        Returns the activity result directly without waiting for a signal.
        """
        return await workflow.execute_activity(
            activity,
            args=list(args),
            start_to_close_timeout=start_to_close_timeout,
        )
