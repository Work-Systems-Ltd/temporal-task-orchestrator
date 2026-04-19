"""Mixin for workflow and pending task listing, counting, and deduplication."""

from __future__ import annotations

import asyncio

from core.models import TaskMeta
from core.workflows import WorkSysFlow
from ui.config import STATUS_QUERIES, TAB_ORDER
from ui.helpers import duration, relative_time, status_name
from ui.models import PaginatedResult, PendingTaskItem, WorkflowItem
from ui.services.temporal.helpers import build_query, group_by_parent, is_assigned_to_user


class ListingsMixin:
    """Workflow listing, counting, and pagination."""

    async def count_workflows(self, query: str | None) -> int:
        """Count workflows matching *query*, deduplicating by workflow ID."""
        seen: dict[str, str] = {}
        async for wf in self._client.list_workflows(query, page_size=100):
            if wf.id not in seen:
                seen[wf.id] = wf.run_id or ""

        async def _is_latest(wf_id: str, run_id: str) -> bool:
            if not run_id:
                return True
            try:
                handle = self._client.get_workflow_handle(wf_id)
                desc = await handle.describe()
                return desc.run_id == run_id
            except Exception:
                return True

        checks = await asyncio.gather(*[_is_latest(wid, rid) for wid, rid in seen.items()])
        return sum(1 for ok in checks if ok)

    async def count_pending(self, wf_type: str | None = None) -> int:
        """Count running workflows that have a pending human task."""
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

    async def get_tab_counts(
        self, wf_type: str | None = None, tabs: list[str] | None = None,
    ) -> dict[str, int]:
        """Return workflow counts for each tab in parallel."""
        tab_list = tabs or TAB_ORDER

        async def _count_tab(tab: str) -> tuple[str, int]:
            if tab == "pending":
                return tab, await self.count_pending(wf_type)
            q = build_query(STATUS_QUERIES[tab], wf_type)
            return tab, await self.count_workflows(q)

        results = await asyncio.gather(*[_count_tab(t) for t in tab_list])
        return dict(results)

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
        """List pending human tasks with access and assignment filtering."""
        all_pending: list[PendingTaskItem] = []
        query = 'ExecutionStatus="Running"'
        if wf_type:
            query += f' AND WorkflowType="{wf_type}"'

        async for wf in self._client.list_workflows(query):
            try:
                handle = self._client.get_workflow_handle(wf.id)
                raw = await handle.query(WorkSysFlow.get_pending_task)
                if not raw:
                    continue

                meta = await self._sanitize_assignment(TaskMeta.model_validate_json(raw))

                if search:
                    haystack = (
                        f"{wf.id} {meta.title} "
                        f"{meta.description} {wf.workflow_type or ''}"
                    ).lower()
                    if search.lower() not in haystack:
                        continue

                # Access filter — non-admins only see tasks they can act on
                if not is_admin:
                    if not is_assigned_to_user(
                        meta.assigned_user, meta.assigned_group,
                        user_slug, user_group_slugs or [],
                    ):
                        continue

                # Assignment sub-filter (tabs within visible tasks)
                if assignment == "mine":
                    if not meta.assigned_user or meta.assigned_user != user_slug:
                        continue
                elif assignment == "my_groups":
                    if not meta.assigned_group or meta.assigned_group not in (user_group_slugs or []):
                        continue
                elif assignment == "unassigned":
                    if meta.assigned_user or meta.assigned_group:
                        continue

                all_pending.append(
                    PendingTaskItem(
                        workflow_id=wf.id,
                        workflow_type=wf.workflow_type,
                        task_type=meta.task_type,
                        title=meta.title,
                        description=meta.description,
                        started=relative_time(wf.start_time),
                        assigned_user=meta.assigned_user,
                        assigned_group=meta.assigned_group,
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

    async def _deduplicate_runs(self, items: list[WorkflowItem]) -> list[WorkflowItem]:
        """Remove items that have been superseded by a newer run."""
        if not items:
            return items

        async def _is_latest(item: WorkflowItem) -> bool:
            if not item.run_id:
                return True
            try:
                handle = self._client.get_workflow_handle(item.workflow_id)
                desc = await handle.describe()
                return desc.run_id == item.run_id
            except Exception:
                return True

        checks = await asyncio.gather(*[_is_latest(item) for item in items])
        return [item for item, ok in zip(items, checks) if ok]

    async def list_workflows(
        self,
        tab: str,
        page: int,
        wf_type: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
    ) -> PaginatedResult:
        """List workflows for a given status tab with pagination."""
        query = build_query(STATUS_QUERIES.get(tab), wf_type)
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
        deduped = await self._deduplicate_runs(items[:size])
        grouped = group_by_parent(deduped)
        return PaginatedResult(items=grouped, has_next=has_next)
