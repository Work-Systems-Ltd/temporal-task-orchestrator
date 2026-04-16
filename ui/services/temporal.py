from __future__ import annotations

import asyncio
from typing import Any

from temporalio.client import Client

from core.models import TaskMeta
from core.workflows import WorkSysFlow, WorkflowDef
from ui.config import STATUS_QUERIES, TAB_ORDER, AppSettings
from ui.helpers import duration, relative_time, status_name
from ui.models import PaginatedResult, PendingTaskItem, TimelineEvent, WorkflowDetail, WorkflowItem


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

    @staticmethod
    def _build_query(base_query: str | None, wf_type: str | None) -> str | None:
        parts: list[str] = []
        if base_query:
            parts.append(base_query)
        if wf_type:
            parts.append(f'WorkflowType="{wf_type}"')
        return " AND ".join(parts) if parts else None

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

        size = per_page or self.page_size
        start = (page - 1) * size
        end = start + size
        return PaginatedResult(
            items=all_pending[start:end],
            has_next=end < len(all_pending),
        )

    async def list_workflows(
        self,
        tab: str,
        page: int,
        wf_type: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
    ) -> PaginatedResult:
        query = self._build_query(STATUS_QUERIES.get(tab), wf_type)
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
                )
            )
            collected += 1

        has_next = len(items) > size
        return PaginatedResult(
            items=items[:size],
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

    async def get_workflow_timeline(self, workflow_id: str) -> list[TimelineEvent]:
        handle = self._client.get_workflow_handle(workflow_id)
        history = await handle.fetch_history()

        # Track scheduled activity names by event_id so we can label completions/failures
        scheduled_activities: dict[int, str] = {}
        events: list[TimelineEvent] = []

        for event in history.events:
            etype = event.event_type
            etime = relative_time(event.event_time.ToDatetime()) if event.event_time else "—"
            eid = event.event_id

            # Workflow lifecycle
            if etype == 1:  # WORKFLOW_EXECUTION_STARTED
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow started", status="completed"))
            elif etype == 2:  # WORKFLOW_EXECUTION_COMPLETED
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow completed", status="completed"))
            elif etype == 3:  # WORKFLOW_EXECUTION_FAILED
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow failed", status="failed"))

            # Activity lifecycle
            elif etype == 10:  # ACTIVITY_TASK_SCHEDULED
                attrs = event.activity_task_scheduled_event_attributes
                name = attrs.activity_type.name if attrs and attrs.activity_type else "unknown"
                scheduled_activities[eid] = name
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=f"{name}", status="info", detail="Scheduled"))
            elif etype == 12:  # ACTIVITY_TASK_COMPLETED
                attrs = event.activity_task_completed_event_attributes
                sched_id = attrs.scheduled_event_id if attrs else 0
                name = scheduled_activities.get(sched_id, "activity")
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=f"{name}", status="completed", detail="Completed"))
            elif etype == 13:  # ACTIVITY_TASK_FAILED
                attrs = event.activity_task_failed_event_attributes
                sched_id = attrs.scheduled_event_id if attrs else 0
                name = scheduled_activities.get(sched_id, "activity")
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=f"{name}", status="failed", detail="Failed"))

            # Signals
            elif etype == 26:  # WORKFLOW_EXECUTION_SIGNALED
                attrs = event.workflow_execution_signaled_event_attributes
                sig_name = attrs.signal_name if attrs else "signal"
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=f"Signal: {sig_name}", status="info"))

            # Child workflows
            elif etype == 31:  # CHILD_WORKFLOW_EXECUTION_STARTED
                attrs = event.child_workflow_execution_started_event_attributes
                wf_type = attrs.workflow_type.name if attrs and attrs.workflow_type else "child"
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=f"Child: {wf_type}", status="info", detail="Started"))
            elif etype == 32:  # CHILD_WORKFLOW_EXECUTION_COMPLETED
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Child workflow", status="completed", detail="Completed"))
            elif etype == 33:  # CHILD_WORKFLOW_EXECUTION_FAILED
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Child workflow", status="failed", detail="Failed"))

        return events

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
