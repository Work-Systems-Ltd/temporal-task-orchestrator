from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from temporalio.client import Client

from core.models import TaskMeta
from core.workflows import WorkSysFlow, WorkflowDef
from ui.config import STATUS_QUERIES, TAB_ORDER, AppSettings
from ui.helpers import duration, relative_time, status_name
from ui.models import GraphNode, PaginatedResult, PendingTaskItem, TimelineEvent, TimelineStats, WorkflowDetail, WorkflowItem


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

    # Temporal fields that support ORDER BY
    SORTABLE_FIELDS: dict[str, str] = {
        "started": "StartTime",
        "closed": "CloseTime",
    }

    @classmethod
    def _build_query(cls, base_query: str | None, wf_type: str | None, sort: str | None = None, sort_dir: str | None = None) -> str | None:
        parts: list[str] = []
        if base_query:
            parts.append(base_query)
        if wf_type:
            parts.append(f'WorkflowType="{wf_type}"')
        q = " AND ".join(parts) if parts else None

        temporal_field = cls.SORTABLE_FIELDS.get(sort or "")
        if temporal_field:
            direction = "ASC" if sort_dir == "asc" else "DESC"
            order_clause = f"ORDER BY {temporal_field} {direction}"
            q = f"{q} {order_clause}" if q else order_clause

        return q

    async def count_workflows(self, query: str | None) -> int:
        count = 0
        async for _ in self._client.list_workflows(query, page_size=100):
            count += 1
        return count

    async def count_pending(self, wf_type: str | None = None) -> int:
        count = 0
        query = 'ExecutionStatus="Running"'
        if wf_type:
            query += f' AND WorkflowType="{wf_type}"'
        async for wf in self._client.list_workflows(query, page_size=100):
            try:
                handle = self._client.get_workflow_handle(wf.id)
                raw = await handle.query(WorkSysFlow.get_pending_task)
                if raw:
                    count += 1
            except Exception:
                continue
        return count

    async def get_tab_counts(self, wf_type: str | None = None) -> dict[str, int]:
        async def _count_tab(tab: str) -> tuple[str, int]:
            if tab == "pending":
                return tab, await self.count_pending(wf_type)
            q = self._build_query(STATUS_QUERIES[tab], wf_type)
            return tab, await self.count_workflows(q)

        results = await asyncio.gather(*[_count_tab(t) for t in TAB_ORDER])
        return dict(results)

    @staticmethod
    def _group_by_parent(items: list) -> list:
        """Group child workflows under their parents using ID convention.

        Children have IDs like "{parent_id}-{suffix}". Attach them to
        the parent's children list and remove them from the top-level.
        """
        by_id = {item.workflow_id: item for item in items}
        children_ids: set[str] = set()

        for item in items:
            parts = item.workflow_id.rsplit("-", 1)
            if len(parts) == 2:
                potential_parent = parts[0]
                if potential_parent in by_id and potential_parent != item.workflow_id:
                    parent = by_id[potential_parent]
                    parent.children.append(item.model_dump())
                    item.parent_id = potential_parent
                    children_ids.add(item.workflow_id)

        return [item for item in items if item.workflow_id not in children_ids]

    async def list_pending(
        self,
        page: int,
        wf_type: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
    ) -> PaginatedResult:
        all_pending: list[PendingTaskItem] = []
        query = 'ExecutionStatus="Running"'
        if wf_type:
            query += f' AND WorkflowType="{wf_type}"'
        async for wf in self._client.list_workflows(query):
            try:
                handle = self._client.get_workflow_handle(wf.id)
                raw = await handle.query(WorkSysFlow.get_pending_task)
                if raw:
                    meta = TaskMeta.model_validate_json(raw)
                    if search:
                        haystack = (
                            f"{wf.id} {meta.title} "
                            f"{meta.description} {wf.workflow_type or ''}"
                        ).lower()
                        if search.lower() not in haystack:
                            continue
                    all_pending.append(
                        PendingTaskItem(
                            workflow_id=wf.id,
                            workflow_type=wf.workflow_type,
                            task_type=meta.task_type,
                            title=meta.title,
                            description=meta.description,
                            started=relative_time(wf.start_time),
                        )
                    )
            except Exception:
                continue

        grouped = self._group_by_parent(all_pending)
        size = per_page or self.page_size
        start = (page - 1) * size
        end = start + size
        return PaginatedResult(
            items=grouped[start:end],
            has_next=end < len(grouped),
        )

    async def list_workflows(
        self,
        tab: str,
        page: int,
        wf_type: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
        sort: str | None = None,
        sort_dir: str | None = None,
    ) -> PaginatedResult:
        query = self._build_query(STATUS_QUERIES.get(tab), wf_type, sort, sort_dir)
        items: list[WorkflowItem] = []
        size = per_page or self.page_size
        skip = (page - 1) * size
        skipped = 0
        collected = 0

        async for wf in self._client.list_workflows(query, page_size=size * 4):
            if search:
                haystack = f"{wf.id} {wf.workflow_type or ''}".lower()
                if search.lower() not in haystack:
                    continue

            if skipped < skip:
                skipped += 1
                continue

            if collected >= size + 1:
                break

            items.append(
                WorkflowItem(
                    workflow_id=wf.id,
                    workflow_type=wf.workflow_type or "—",
                    status=status_name(wf.status),
                    started=relative_time(wf.start_time),
                    closed=relative_time(wf.close_time),
                    duration=duration(wf.start_time, wf.close_time),
                    task_queue=wf.task_queue or "—",
                    run_id=wf.run_id or "",
                    history_length=wf.history_length or 0,
                    parent_id=wf.parent_id or "",
                )
            )
            collected += 1

        has_next = len(items) > size
        grouped = self._group_by_parent(items[:size])
        return PaginatedResult(
            items=grouped,
            has_next=has_next,
        )

    async def get_workflow_detail(self, workflow_id: str) -> WorkflowDetail | None:
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            desc = await handle.describe()
            return WorkflowDetail(
                workflow_id=desc.id,
                run_id=desc.run_id,
                workflow_type=desc.workflow_type or "—",
                status=status_name(desc.status),
                started=relative_time(desc.start_time),
                closed=relative_time(desc.close_time),
                duration=duration(desc.start_time, desc.close_time),
                task_queue=desc.task_queue or "—",
                history_length=desc.history_length,
                parent_id=desc.parent_id,
            )
        except Exception:
            return None

    @staticmethod
    def _ms_duration(start: datetime, end: datetime) -> str:
        """Format a duration between two datetimes as a human-readable string."""
        diff = (end - start).total_seconds()
        if diff < 0.001:
            return "<1ms"
        if diff < 1:
            return f"{int(diff * 1000)}ms"
        if diff < 60:
            return f"{diff:.1f}s"
        minutes = int(diff) // 60
        secs = int(diff) % 60
        if minutes < 60:
            return f"{minutes}m {secs}s"
        hours = minutes // 60
        return f"{hours}h {minutes % 60}m"

    async def get_workflow_timeline(self, workflow_id: str) -> tuple[list[TimelineEvent], TimelineStats]:
        handle = self._client.get_workflow_handle(workflow_id)
        history = await handle.fetch_history()

        # Track scheduled activities/children so we can collapse into single events
        scheduled_activities: dict[int, tuple[str, datetime]] = {}  # sched_event_id -> (name, scheduled_at)
        child_workflows: dict[int, tuple[str, str]] = {}  # initiated_event_id -> (type, child_wf_id)
        events: list[TimelineEvent] = []

        # For stats
        total_activity_secs = 0.0
        last_activity_end: datetime | None = None
        total_wait_secs = 0.0
        workflow_start: datetime | None = None
        workflow_end: datetime | None = None
        workflow_input: str = ""
        workflow_output: str = ""

        def _ts(event) -> datetime:
            return event.event_time.ToDatetime(tzinfo=timezone.utc)

        for event in history.events:
            etype = event.event_type
            etime = relative_time(_ts(event)) if event.event_time else "—"
            eid = event.event_id

            # Workflow lifecycle
            if etype == 1:  # WORKFLOW_EXECUTION_STARTED
                workflow_start = _ts(event)
                attrs = event.workflow_execution_started_event_attributes
                if attrs and attrs.input and attrs.input.payloads:
                    try:
                        workflow_input = attrs.input.payloads[0].data.decode("utf-8")
                    except Exception:
                        pass
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow started", status="completed"))
            elif etype == 2:  # WORKFLOW_EXECUTION_COMPLETED
                workflow_end = _ts(event)
                attrs = event.workflow_execution_completed_event_attributes
                if attrs and attrs.result and attrs.result.payloads:
                    try:
                        workflow_output = attrs.result.payloads[0].data.decode("utf-8")
                    except Exception:
                        pass
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow completed", status="completed"))
            elif etype == 3:  # WORKFLOW_EXECUTION_FAILED
                workflow_end = _ts(event)
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow failed", status="failed"))

            # Activity lifecycle — only emit on completion/failure (skip scheduled)
            elif etype == 10:  # ACTIVITY_TASK_SCHEDULED
                attrs = event.activity_task_scheduled_event_attributes
                name = attrs.activity_type.name if attrs and attrs.activity_type else "unknown"
                scheduled_activities[eid] = (name, _ts(event))
            elif etype == 12:  # ACTIVITY_TASK_COMPLETED
                attrs = event.activity_task_completed_event_attributes
                sched_id = attrs.scheduled_event_id if attrs else 0
                name, sched_time = scheduled_activities.get(sched_id, ("activity", _ts(event)))
                act_duration = (_ts(event) - sched_time).total_seconds()
                total_activity_secs += act_duration
                last_activity_end = _ts(event)
                dur_str = self._ms_duration(sched_time, _ts(event))
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=name, status="completed", duration=dur_str))
            elif etype == 13:  # ACTIVITY_TASK_FAILED
                attrs = event.activity_task_failed_event_attributes
                sched_id = attrs.scheduled_event_id if attrs else 0
                name, sched_time = scheduled_activities.get(sched_id, ("activity", _ts(event)))
                act_duration = (_ts(event) - sched_time).total_seconds()
                total_activity_secs += act_duration
                dur_str = self._ms_duration(sched_time, _ts(event))
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=name, status="failed", duration=dur_str))

            # Signals — measure wait time from last activity
            elif etype == 26:  # WORKFLOW_EXECUTION_SIGNALED
                attrs = event.workflow_execution_signaled_event_attributes
                sig_name = attrs.signal_name if attrs else "signal"
                dur_str = ""
                if last_activity_end:
                    wait = (_ts(event) - last_activity_end).total_seconds()
                    total_wait_secs += wait
                    dur_str = self._ms_duration(last_activity_end, _ts(event))
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=f"Signal: {sig_name}", status="info", duration=dur_str))

            # Child workflows — track on initiation, emit on start/complete/fail
            elif etype == 29:  # START_CHILD_WORKFLOW_EXECUTION_INITIATED
                attrs = event.start_child_workflow_execution_initiated_event_attributes
                wf_type = attrs.workflow_type.name if attrs and attrs.workflow_type else "child"
                child_wf_id = attrs.workflow_id if attrs else ""
                child_workflows[eid] = (wf_type, child_wf_id)
            elif etype == 31:  # CHILD_WORKFLOW_EXECUTION_STARTED
                attrs = event.child_workflow_execution_started_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                wf_type, child_wf_id = child_workflows.get(init_id, ("child", ""))
                if not child_wf_id and attrs and attrs.workflow_execution:
                    child_wf_id = attrs.workflow_execution.workflow_id
                link = f"/workflow/{child_wf_id}" if child_wf_id else ""
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=wf_type, status="info", detail="Child workflow", link=link))
            elif etype == 32:  # CHILD_WORKFLOW_EXECUTION_COMPLETED
                attrs = event.child_workflow_execution_completed_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                wf_type, child_wf_id = child_workflows.get(init_id, ("child", ""))
                link = f"/workflow/{child_wf_id}" if child_wf_id else ""
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=wf_type, status="completed", detail="Child completed", link=link))
            elif etype == 33:  # CHILD_WORKFLOW_EXECUTION_FAILED
                attrs = event.child_workflow_execution_failed_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                wf_type, child_wf_id = child_workflows.get(init_id, ("child", ""))
                link = f"/workflow/{child_wf_id}" if child_wf_id else ""
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=wf_type, status="failed", detail="Child failed", link=link))

        _epoch = datetime.min.replace(tzinfo=timezone.utc)
        stats = TimelineStats(
            activity_time=self._ms_duration(_epoch, _epoch + timedelta(seconds=total_activity_secs)) if total_activity_secs > 0 else "—",
            wait_time=self._ms_duration(_epoch, _epoch + timedelta(seconds=total_wait_secs)) if total_wait_secs > 0 else "—",
            total_time=self._ms_duration(workflow_start, workflow_end) if workflow_start and workflow_end else "—",
            workflow_input=workflow_input,
            workflow_output=workflow_output,
        )

        return events, stats

    async def _find_children(self, parent_wf_id: str) -> list[tuple[str, str, str]]:
        """Return (wf_type, child_wf_id, status) for direct children of a workflow."""
        try:
            handle = self._client.get_workflow_handle(parent_wf_id)
            history = await handle.fetch_history()
        except Exception:
            return []

        initiated: dict[int, tuple[str, str]] = {}  # init_event_id -> (type, child_id)
        child_status: dict[str, str] = {}  # child_id -> status

        for event in history.events:
            etype = event.event_type
            eid = event.event_id

            if etype == 29:  # START_CHILD_WORKFLOW_EXECUTION_INITIATED
                attrs = event.start_child_workflow_execution_initiated_event_attributes
                wf_type = attrs.workflow_type.name if attrs and attrs.workflow_type else "child"
                child_wf_id = attrs.workflow_id if attrs else ""
                if child_wf_id:
                    initiated[eid] = (wf_type, child_wf_id)
                    child_status[child_wf_id] = "pending"
            elif etype == 31:  # CHILD_WORKFLOW_EXECUTION_STARTED
                attrs = event.child_workflow_execution_started_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                if init_id in initiated:
                    _, child_wf_id = initiated[init_id]
                    child_status[child_wf_id] = "running"
            elif etype == 32:  # CHILD_WORKFLOW_EXECUTION_COMPLETED
                attrs = event.child_workflow_execution_completed_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                if init_id in initiated:
                    _, child_wf_id = initiated[init_id]
                    child_status[child_wf_id] = "completed"
            elif etype == 33:  # CHILD_WORKFLOW_EXECUTION_FAILED
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
        self, wf_id: str, wf_type: str, status: str, current_id: str, depth: int = 0, max_depth: int = 4,
    ) -> GraphNode:
        """Recursively build a GraphNode tree."""
        node = GraphNode(
            workflow_id=wf_id,
            workflow_type=wf_type,
            status=status,
            label=wf_type,
            is_current=(wf_id == current_id),
        )
        if depth < max_depth:
            child_infos = await self._find_children(wf_id)
            if child_infos:
                node.children = await asyncio.gather(*[
                    self._build_graph_node(cid, ctype, cstatus, current_id, depth + 1, max_depth)
                    for ctype, cid, cstatus in child_infos
                ])
        return node

    async def get_workflow_graph(self, workflow_id: str, detail: WorkflowDetail) -> GraphNode | None:
        """Build a recursive tree of parent → children workflows.

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

        # Only show graph if there are children somewhere
        return root if root.children else None

    async def get_all_pending_tasks(self, graph: GraphNode | None, workflow_id: str) -> list[dict]:
        """Collect pending tasks from the current workflow and all descendants in the graph."""
        wf_ids: list[str] = []

        def _collect_running(node: GraphNode) -> None:
            if node.status == "running":
                wf_ids.append(node.workflow_id)
            for child in node.children:
                _collect_running(child)

        if graph:
            _collect_running(graph)
        elif workflow_id not in [w for w in wf_ids]:
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

    async def get_pending_task(self, workflow_id: str) -> TaskMeta | None:
        handle = self._client.get_workflow_handle(workflow_id)
        raw = await handle.query(WorkSysFlow.get_pending_task)
        if not raw:
            return None
        return TaskMeta.model_validate_json(raw)

    async def signal_complete(self, workflow_id: str, data: str) -> None:
        handle = self._client.get_workflow_handle(workflow_id)
        await handle.signal(WorkSysFlow.complete_human_task, data)

    async def start_workflow(
        self, wf_def: WorkflowDef, input_value: Any, workflow_id: str
    ) -> str:
        await self._client.start_workflow(
            wf_def.workflow_cls.run,
            input_value,
            id=workflow_id,
            task_queue=self.task_queue,
        )
        return workflow_id
