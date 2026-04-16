from __future__ import annotations

import json
from typing import Any

from temporalio import workflow

from models import TaskMeta


class HumanTaskWorkflow:
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

    @workflow.query
    def get_pending_task(self) -> str:
        if self._pending_task:
            return self._pending_task.model_dump_json()
        return ""

    async def wait_for_human_task(self, task_meta: TaskMeta) -> dict[str, Any]:
        """Set the pending task and block until the human signal arrives.

        Returns the parsed human task data dict.
        """
        self._pending_task = task_meta
        await workflow.wait_condition(lambda: self._human_task_complete)
        self._pending_task = None
        self._human_task_complete = False
        assert self._human_task_data is not None
        data = self._human_task_data
        self._human_task_data = None
        return data
