"""Mixin for workflow graph building — parent/child tree with activity and task nodes."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from core.workflows import WorkSysFlow
from ui.helpers import duration, relative_time
from ui.models import GraphNode, WorkflowDetail
from ui.services.temporal.helpers import ms_duration
from ui.services.temporal.event_types import (
    ACTIVITY_TASK_SCHEDULED, ACTIVITY_TASK_COMPLETED, ACTIVITY_TASK_FAILED_LEGACY,
    WORKFLOW_EXECUTION_SIGNALED,
    START_CHILD_WORKFLOW_EXECUTION_INITIATED, CHILD_WORKFLOW_EXECUTION_STARTED,
    CHILD_WORKFLOW_EXECUTION_COMPLETED, CHILD_WORKFLOW_EXECUTION_FAILED,
)

logger = logging.getLogger(__name__)


class GraphMixin:
    """Workflow graph tree construction and pending task collection."""

    async def get_workflow_graph(
        self, workflow_id: str, detail: WorkflowDetail,
    ) -> GraphNode | None:
        """Build a recursive tree of parent -> children workflows.

        If viewing a child, resolve up to the root first.
        Returns None for standalone workflows with no children.
        """
        root_id = detail.parent_id or workflow_id
        root_detail = detail if not detail.parent_id else await self.get_workflow_detail(root_id)
        if not root_detail:
            return None

        root = await self._build_graph_node(
            root_id, root_detail.workflow_type, root_detail.status, workflow_id,
        )
        return root if root.children else None

    async def get_all_pending_tasks(
        self, graph: GraphNode | None, workflow_id: str,
    ) -> list[dict]:
        """Collect pending tasks from the current workflow and all descendants."""
        wf_ids: list[str] = []

        def _collect_running(node: GraphNode) -> None:
            if node.node_type == "task":
                return
            if node.status == "running":
                wf_ids.append(node.workflow_id)
            for child in node.children:
                _collect_running(child)

        if graph:
            _collect_running(graph)
        elif workflow_id not in wf_ids:
            wf_ids.append(workflow_id)

        if not wf_ids:
            return []

        async def _fetch(wid: str) -> dict | None:
            meta = await self.get_pending_task(wid)
            if meta:
                return {"workflow_id": wid, **meta.model_dump()}
            return None

        results = await asyncio.gather(*[_fetch(wid) for wid in wf_ids])
        return [r for r in results if r is not None]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _find_children(self, parent_wf_id: str) -> list[tuple[str, str, str]]:
        """Return (wf_type, child_wf_id, status) for direct children."""
        try:
            handle = self._client.get_workflow_handle(parent_wf_id)
            history = await handle.fetch_history()
        except Exception as exc:
            logger.debug("Graph build error: %s", exc)
            return []

        initiated: dict[int, tuple[str, str]] = {}
        child_status: dict[str, str] = {}

        for event in history.events:
            etype = event.event_type
            eid = event.event_id

            if etype == START_CHILD_WORKFLOW_EXECUTION_INITIATED:  # START_CHILD_WORKFLOW_EXECUTION_INITIATED
                attrs = event.start_child_workflow_execution_initiated_event_attributes
                wf_type = attrs.workflow_type.name if attrs and attrs.workflow_type else "child"
                child_wf_id = attrs.workflow_id if attrs else ""
                if child_wf_id:
                    initiated[eid] = (wf_type, child_wf_id)
                    child_status[child_wf_id] = "pending"
            elif etype == CHILD_WORKFLOW_EXECUTION_STARTED:  # CHILD_WORKFLOW_EXECUTION_STARTED
                attrs = event.child_workflow_execution_started_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                if init_id in initiated:
                    _, child_wf_id = initiated[init_id]
                    child_status[child_wf_id] = "running"
            elif etype == CHILD_WORKFLOW_EXECUTION_COMPLETED:  # CHILD_WORKFLOW_EXECUTION_COMPLETED
                attrs = event.child_workflow_execution_completed_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                if init_id in initiated:
                    _, child_wf_id = initiated[init_id]
                    child_status[child_wf_id] = "completed"
            elif etype == CHILD_WORKFLOW_EXECUTION_FAILED:  # CHILD_WORKFLOW_EXECUTION_FAILED
                attrs = event.child_workflow_execution_failed_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                if init_id in initiated:
                    _, child_wf_id = initiated[init_id]
                    child_status[child_wf_id] = "failed"

        return [
            (wf_type, child_wf_id, child_status.get(child_wf_id, "pending"))
            for _, (wf_type, child_wf_id) in sorted(initiated.items())
        ]

    async def _build_graph_node(
        self,
        wf_id: str,
        wf_type: str,
        status: str,
        current_id: str,
        depth: int = 0,
        max_depth: int = 4,
    ) -> GraphNode:
        """Recursively build a GraphNode tree with activity and task child nodes."""
        started_str = ""
        duration_str = ""
        try:
            handle = self._client.get_workflow_handle(wf_id)
            desc = await handle.describe()
            started_str = relative_time(desc.start_time)
            duration_str = duration(desc.start_time, desc.close_time)
        except Exception as exc:
            logger.debug("Graph build error: %s", exc)

        node = GraphNode(
            workflow_id=wf_id,
            workflow_type=wf_type,
            status=status,
            label=wf_type,
            is_current=(wf_id == current_id),
            started=started_str,
            duration=duration_str,
        )

        # Discover child workflows
        if depth < max_depth:
            child_infos = await self._find_children(wf_id)
            if child_infos:
                node.children = await asyncio.gather(*[
                    self._build_graph_node(cid, ctype, cstatus, current_id, depth + 1, max_depth)
                    for ctype, cid, cstatus in child_infos
                ])

        # Attach activity and human task nodes from history
        node.node_type = "workflow"
        try:
            handle = self._client.get_workflow_handle(wf_id)
            history = await handle.fetch_history()

            scheduled: dict[int, tuple[str, datetime]] = {}
            has_human_task = False

            for event in history.events:
                etype = event.event_type

                if etype == ACTIVITY_TASK_SCHEDULED:  # ACTIVITY_TASK_SCHEDULED
                    attrs = event.activity_task_scheduled_event_attributes
                    if attrs:
                        scheduled[event.event_id] = (
                            attrs.activity_type.name if attrs.activity_type else "Activity",
                            event.event_time.ToDatetime() if event.event_time else None,
                        )

                elif etype == ACTIVITY_TASK_COMPLETED:  # ACTIVITY_TASK_COMPLETED
                    attrs = event.activity_task_completed_event_attributes
                    sched_id = attrs.scheduled_event_id if attrs else 0
                    if sched_id in scheduled:
                        name, sched_time = scheduled[sched_id]
                        dur = ""
                        if sched_time and event.event_time:
                            dur = ms_duration(sched_time, event.event_time.ToDatetime())
                        node.children.append(GraphNode(
                            workflow_id=wf_id, workflow_type=wf_type,
                            status="completed", label=name,
                            node_type="activity", is_current=False, duration=dur,
                        ))

                elif etype == ACTIVITY_TASK_FAILED_LEGACY:  # ACTIVITY_TASK_FAILED
                    attrs = event.activity_task_failed_event_attributes
                    sched_id = attrs.scheduled_event_id if attrs else 0
                    if sched_id in scheduled:
                        name, _ = scheduled[sched_id]
                        node.children.append(GraphNode(
                            workflow_id=wf_id, workflow_type=wf_type,
                            status="failed", label=name,
                            node_type="activity", is_current=False,
                        ))

                elif etype == WORKFLOW_EXECUTION_SIGNALED:  # WORKFLOW_EXECUTION_SIGNALED
                    attrs = event.workflow_execution_signaled_event_attributes
                    if attrs and attrs.signal_name == "complete_human_task":
                        has_human_task = True
                        task_status = "completed" if node.status == "completed" else node.status
                        node.children.append(GraphNode(
                            workflow_id=wf_id, workflow_type=wf_type,
                            status=task_status, label="Human Task",
                            node_type="task", is_current=False,
                        ))

            # If running and has a pending human task, add it
            if node.status == "running" and not has_human_task:
                try:
                    meta = await self.get_pending_task(wf_id)
                    if meta:
                        node.children.append(GraphNode(
                            workflow_id=wf_id, workflow_type=wf_type,
                            status="running", label=meta.title or meta.task_type,
                            node_type="task", is_current=False, started=started_str,
                        ))
                except Exception as exc:
                    logger.debug("Graph node error: %s", exc)

        except Exception as exc:
            logger.debug("Graph build error: %s", exc)

        return node
