from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, ClassVar, Type

from temporalio import workflow
from temporalio.common import RetryPolicy

from core.models import TaskMeta
from core.tasks.base import HumanTask

from abc import ABC


# Import activity input models — these are plain Pydantic models, safe in workflow sandbox
with workflow.unsafe.imports_passed_through():
    from core.activities.task_persistence import (
        CompleteTaskInput,
        CreateTaskInput,
        UpdateTaskInput,
    )
    from core.activities.workflow_persistence import (
        CompleteWorkflowInput,
        CreateWorkflowInput,
        FailWorkflowInput,
    )


class WorkSysFlow(ABC):
    """Base class for workflows that pause for human input.

    Subclasses must be decorated with @register_workflow and @workflow.defn,
    and must define a @workflow.run method and an input_task ClassVar.
    """

    input_task: ClassVar[Type[HumanTask] | None]
    _workflow_key: ClassVar[str] = ""

    def __init__(self) -> None:
        self._human_task_complete: bool = False
        self._human_task_data: dict[str, Any] | None = None
        self._pending_task: TaskMeta | None = None

    @workflow.signal
    async def complete_human_task(self, data: str) -> None:
        try:
            self._human_task_data = json.loads(data)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"Invalid task completion data: {exc}") from exc
        self._human_task_complete = True

    @workflow.signal
    async def reassign_task(self, data: str) -> None:
        """Update the assignment on the current pending task."""
        if self._pending_task:
            try:
                payload = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return  # ignore malformed reassign signals
            self._pending_task = self._pending_task.model_copy(update=payload)

    @workflow.query
    def get_pending_task(self) -> str:
        if self._pending_task:
            return self._pending_task.model_dump_json()
        return ""

    async def _persist_task_created(self, task_meta: TaskMeta) -> None:
        """Persist a new task record to the database via activity."""
        create_input = CreateTaskInput(
            task_id=task_meta.task_id,
            workflow_id=workflow.info().workflow_id,
            run_id=workflow.info().run_id,
            task_type=task_meta.task_type,
            title=task_meta.title,
            description=task_meta.description,
            priority=task_meta.priority,
            assigned_user=task_meta.assigned_user,
            assigned_group=task_meta.assigned_group,
        )
        await workflow.execute_activity(
            "create_task_record",
            create_input.model_dump_json(),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

    async def _persist_task_completed(
        self, task_id: str, form_data: dict | None, completed_by: str = ""
    ) -> None:
        """Mark a task as completed in the database via activity."""
        complete_input = CompleteTaskInput(
            task_id=task_id,
            form_data=form_data,
            completed_by=completed_by,
        )
        await workflow.execute_activity(
            "complete_task_record",
            complete_input.model_dump_json(),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

    async def _persist_workflow_started(self, input_data: Any = None) -> None:
        """Persist a new workflow record to the database via activity."""
        info = workflow.info()

        # Serialize input_data to JSON string
        input_str = ""
        if input_data is not None:
            try:
                if hasattr(input_data, "model_dump_json"):
                    input_str = input_data.model_dump_json()
                elif hasattr(input_data, "model_dump"):
                    input_str = json.dumps(input_data.model_dump())
                else:
                    input_str = json.dumps(input_data)
            except (TypeError, ValueError):
                input_str = str(input_data)

        create_input = CreateWorkflowInput(
            workflow_id=info.workflow_id,
            run_id=info.run_id,
            workflow_type=info.workflow_type,
            workflow_key=self._workflow_key or info.workflow_type,
            parent_workflow_id=info.parent_id or "",
            input_data=input_str,
            task_queue=info.task_queue,
        )
        await workflow.execute_activity(
            "create_workflow_record",
            create_input.model_dump_json(),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

    async def _persist_workflow_completed(self, output: Any = None) -> None:
        """Mark workflow as completed in the database via activity."""
        output_str = ""
        if output is not None:
            try:
                if hasattr(output, "model_dump_json"):
                    output_str = output.model_dump_json()
                elif hasattr(output, "model_dump"):
                    output_str = json.dumps(output.model_dump())
                else:
                    output_str = json.dumps(output)
            except (TypeError, ValueError):
                output_str = str(output)

        complete_input = CompleteWorkflowInput(
            workflow_id=workflow.info().workflow_id,
            output_data=output_str,
        )
        await workflow.execute_activity(
            "complete_workflow_record",
            complete_input.model_dump_json(),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

    async def _persist_workflow_failed(self, error: str) -> None:
        """Mark workflow as failed in the database via activity."""
        fail_input = FailWorkflowInput(
            workflow_id=workflow.info().workflow_id,
            error_message=error,
        )
        await workflow.execute_activity(
            "fail_workflow_record",
            fail_input.model_dump_json(),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

    async def _wait_for_signal(self, task_meta: TaskMeta) -> dict[str, Any]:
        """Internal: set pending task and block until the human signal arrives."""
        # Persist task creation to database
        await self._persist_task_created(task_meta)

        self._pending_task = task_meta
        await workflow.wait_condition(lambda: self._human_task_complete)
        self._pending_task = None
        self._human_task_complete = False
        if self._human_task_data is None:
            raise RuntimeError("Human task signal received but no data was set")
        data = self._human_task_data
        self._human_task_data = None

        # Persist task completion to database
        await self._persist_task_completed(task_meta.task_id, data)

        return data

    async def create_human_task(
        self,
        task: Type[HumanTask],
        *,
        title: str,
        description: str = "",
        assigned_user: str = "",
        assigned_group: str = "",
        priority: str = "medium",
    ) -> dict[str, Any]:
        """Block until a human completes the given task type.

        Args:
            task: The HumanTask class (used for type-safe task_type resolution).
            title: Human-readable task title shown in the UI.
            description: Task description shown in the UI.
            assigned_user: Optional user slug to assign the task to.
            assigned_group: Optional group slug to assign the task to.
            priority: Task priority level (critical, high, medium, low).

        Returns:
            The parsed human task data dict.
        """
        task_id = str(workflow.uuid4())
        task_meta = TaskMeta(
            task_id=task_id,
            task_type=task.task_type,
            title=title,
            description=description,
            assigned_user=assigned_user,
            assigned_group=assigned_group,
            priority=priority,
        )
        return await self._wait_for_signal(task_meta)

    _DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=3)

    async def create_system_task(
        self,
        activity_fn,
        *args,
        start_to_close_timeout: timedelta = timedelta(seconds=10),
        retry_policy: RetryPolicy | None = None,
    ) -> Any:
        """Execute a system task activity.

        Args:
            activity_fn: The @activity.defn function to execute.
            *args: Positional arguments passed to the activity.
            start_to_close_timeout: Temporal activity timeout.
            retry_policy: Optional Temporal RetryPolicy. Defaults to 3 max attempts.

        Returns the activity result directly without waiting for a signal.
        """
        return await workflow.execute_activity(
            activity_fn,
            args=list(args),
            retry_policy=retry_policy or self._DEFAULT_RETRY_POLICY,
            start_to_close_timeout=start_to_close_timeout,
        )
