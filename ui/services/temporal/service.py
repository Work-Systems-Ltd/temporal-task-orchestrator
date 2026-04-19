"""TemporalService — composed from focused mixins."""

from __future__ import annotations

import json
from typing import Any

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy

from core.workflows import WorkflowDef, get_all_workflows
from ui.config import AppSettings

from .mixins import DetailMixin, GraphMixin, ListingsMixin, TasksMixin


class TemporalService(TasksMixin, ListingsMixin, DetailMixin, GraphMixin):
    """Unified service for all Temporal interactions.

    Implementation is split across mixins:
      - TasksMixin:    pending task queries, completion/reassign signals
      - ListingsMixin: workflow/task listing, counting, pagination
      - DetailMixin:   workflow detail, timeline, run history
      - GraphMixin:    workflow graph tree, child discovery
    """

    def __init__(self, client: Client, settings: AppSettings) -> None:
        self._client = client
        self._settings = settings

    @property
    def page_size(self) -> int:
        return self._settings.page_size

    @property
    def task_queue(self) -> str:
        return self._settings.task_queue

    # ------------------------------------------------------------------
    # Workflow execution
    # ------------------------------------------------------------------

    async def start_workflow(
        self, wf_def: WorkflowDef, input_value: Any, workflow_id: str,
    ) -> str:
        await self._client.start_workflow(
            wf_def.workflow_cls.run,
            input_value,
            id=workflow_id,
            task_queue=self.task_queue,
        )
        return workflow_id

    async def get_workflow_input(self, workflow_id: str) -> dict | None:
        """Extract the original input dict from a workflow's history."""
        handle = self._client.get_workflow_handle(workflow_id)
        async for event in handle.fetch_history_events():
            attrs = event.workflow_execution_started_event_attributes
            if attrs and attrs.input and attrs.input.payloads:
                return json.loads(attrs.input.payloads[0].data)
        return None

    def get_workflow_def_by_type(self, workflow_type: str) -> WorkflowDef | None:
        """Look up a WorkflowDef by its Temporal workflow type name."""
        for wd in get_all_workflows():
            if wd.workflow_cls.__name__ == workflow_type:
                return wd
        return None

    async def rerun_workflow(self, workflow_id: str, input_value: Any = None) -> str:
        """Re-execute a failed/terminated workflow with the same ID."""
        handle = self._client.get_workflow_handle(workflow_id)
        desc = await handle.describe()

        rerunnable = {"FAILED", "TERMINATED", "TIMED_OUT", "CANCELED"}
        if desc.status.name not in rerunnable:
            raise ValueError(f"Cannot rerun workflow with status {desc.status.name}")

        wf_def = self.get_workflow_def_by_type(desc.workflow_type)
        if not wf_def:
            raise ValueError(f"Unknown workflow type: {desc.workflow_type}")

        if input_value is None:
            raw = await self.get_workflow_input(workflow_id)
            if raw and wf_def.input_task:
                input_value = wf_def.input_task.Model(**raw)
            else:
                input_value = raw

        await self._client.start_workflow(
            wf_def.workflow_cls.run,
            input_value,
            id=workflow_id,
            task_queue=self.task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        )
        return workflow_id
