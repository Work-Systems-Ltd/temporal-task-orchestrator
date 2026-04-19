"""Main TemporalService — thin facade delegating to focused modules."""

from __future__ import annotations

import json
from typing import Any

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy

from core.models import TaskMeta
from core.workflows import WorkflowDef, get_all_workflows
from ui.config import AppSettings
from ui.models import (
    GraphNode,
    PaginatedResult,
    TimelineEvent,
    TimelineStats,
    WorkflowDetail,
)

from . import detail, graph, listings, tasks


class TemporalService:
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
    # Listings
    # ------------------------------------------------------------------

    async def get_tab_counts(
        self, wf_type: str | None = None, tabs: list[str] | None = None,
    ) -> dict[str, int]:
        return await listings.get_tab_counts(self._client, wf_type, tabs)

    async def list_pending(
        self,
        page: int,
        wf_type: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
        assignment: str | None = None,
        user_slug: str = "",
        user_group_slugs: list[str] | None = None,
        is_admin: bool = False,
    ) -> PaginatedResult:
        return await listings.list_pending(
            self._client, page, self.page_size,
            wf_type=wf_type, search=search, per_page=per_page,
            assignment=assignment, user_slug=user_slug,
            user_group_slugs=user_group_slugs, is_admin=is_admin,
        )

    async def list_workflows(
        self,
        tab: str,
        page: int,
        wf_type: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
    ) -> PaginatedResult:
        return await listings.list_workflows(
            self._client, tab, page, self.page_size,
            wf_type=wf_type, search=search, per_page=per_page,
        )

    # ------------------------------------------------------------------
    # Detail / timeline / run history
    # ------------------------------------------------------------------

    async def get_workflow_detail(
        self, workflow_id: str, run_id: str | None = None,
    ) -> WorkflowDetail | None:
        return await detail.get_workflow_detail(self._client, workflow_id, run_id)

    async def get_run_history(self, workflow_id: str) -> list[dict]:
        return await detail.get_run_history(self._client, workflow_id)

    async def get_workflow_timeline(
        self, workflow_id: str, run_id: str | None = None,
    ) -> tuple[list[TimelineEvent], TimelineStats]:
        return await detail.get_workflow_timeline(self._client, workflow_id, run_id)

    # ------------------------------------------------------------------
    # Graph
    # ------------------------------------------------------------------

    async def get_workflow_graph(
        self, workflow_id: str, detail_obj: WorkflowDetail,
    ) -> GraphNode | None:
        return await graph.get_workflow_graph(self._client, workflow_id, detail_obj)

    async def get_all_pending_tasks(
        self, graph_obj: GraphNode | None, workflow_id: str,
    ) -> list[dict]:
        return await graph.get_all_pending_tasks(self._client, graph_obj, workflow_id)

    # ------------------------------------------------------------------
    # Tasks (pending, signals)
    # ------------------------------------------------------------------

    async def get_pending_task(self, workflow_id: str) -> TaskMeta | None:
        return await tasks.get_pending_task(self._client, workflow_id)

    async def signal_complete(self, workflow_id: str, data: str) -> None:
        return await tasks.signal_complete(self._client, workflow_id, data)

    async def reassign_task(
        self, workflow_id: str, assigned_user: str = "", assigned_group: str = "",
    ) -> None:
        return await tasks.signal_reassign(
            self._client, workflow_id, assigned_user, assigned_group,
        )

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
