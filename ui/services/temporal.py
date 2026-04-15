from __future__ import annotations

import asyncio
import json

from temporalio.client import Client

from ui.config import STATUS_QUERIES, TAB_ORDER, AppSettings
from ui.helpers import duration, relative_time, status_name
from ui.models import PaginatedResult, PendingTaskItem, TaskMeta, WorkflowItem
from workflows.registry import WorkflowDef


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
                raw = await handle.query("get_pending_task")
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
    ) -> PaginatedResult:
        all_pending: list[PendingTaskItem] = []
        query = 'ExecutionStatus="Running"'
        if wf_type:
            query += f' AND WorkflowType="{wf_type}"'
        async for wf in self._client.list_workflows(query):
            try:
                handle = self._client.get_workflow_handle(wf.id)
                raw = await handle.query("get_pending_task")
                if raw:
                    meta = json.loads(raw)
                    if search:
                        haystack = (
                            f"{wf.id} {meta.get('title', '')} "
                            f"{meta.get('description', '')} {wf.workflow_type or ''}"
                        ).lower()
                        if search.lower() not in haystack:
                            continue
                    all_pending.append(
                        PendingTaskItem(
                            workflow_id=wf.id,
                            workflow_type=wf.workflow_type,
                            task_type=meta.get("task_type", ""),
                            title=meta.get("title", ""),
                            description=meta.get("description", ""),
                            started=relative_time(wf.start_time),
                        )
                    )
            except Exception:
                continue

        start = (page - 1) * self.page_size
        end = start + self.page_size
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
    ) -> PaginatedResult:
        query = self._build_query(STATUS_QUERIES.get(tab), wf_type)
        items: list[WorkflowItem] = []
        skip = (page - 1) * self.page_size
        skipped = 0
        collected = 0

        async for wf in self._client.list_workflows(query, page_size=self.page_size * 4):
            if search:
                haystack = f"{wf.id} {wf.workflow_type or ''}".lower()
                if search.lower() not in haystack:
                    continue

            if skipped < skip:
                skipped += 1
                continue

            if collected >= self.page_size + 1:
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

        has_next = len(items) > self.page_size
        return PaginatedResult(
            items=items[: self.page_size],
            has_next=has_next,
        )

    async def get_pending_task(self, workflow_id: str) -> TaskMeta | None:
        handle = self._client.get_workflow_handle(workflow_id)
        raw = await handle.query("get_pending_task")
        if not raw:
            return None
        data = json.loads(raw)
        return TaskMeta(**data)

    async def signal_complete(self, workflow_id: str, data: str) -> None:
        handle = self._client.get_workflow_handle(workflow_id)
        await handle.signal("complete_human_task", data)

    async def start_workflow(
        self, wf_def: WorkflowDef, input_value: str, workflow_id: str
    ) -> str:
        await self._client.start_workflow(
            wf_def.workflow_cls.run,
            input_value,
            id=workflow_id,
            task_queue=self.task_queue,
        )
        return workflow_id
