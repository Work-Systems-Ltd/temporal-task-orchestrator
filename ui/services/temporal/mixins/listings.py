"""Mixin for workflow and pending task listing, counting, and deduplication."""

from __future__ import annotations

import asyncio
import logging

from core.models import TaskMeta
from core.workflows import WorkSysFlow
from ui.config import STATUS_QUERIES, TAB_ORDER
from ui.helpers import duration, relative_time, status_name
from ui.models import PaginatedResult, PendingTaskItem, WorkflowItem
from ui.services.temporal.helpers import build_query, group_by_parent, is_assigned_to_user

logger = logging.getLogger(__name__)


class ListingsMixin:
    """Workflow listing, counting, and pagination."""

    async def count_workflows(self, query: str | None) -> int:
        """Count workflows matching *query* using Temporal's server-side count."""
        result = await self._client.count_workflows(query or "")
        return result.count

    async def count_pending(self, wf_type: str | None = None) -> int:
        """Count running workflows (approximation — counts all running, not just those with pending tasks)."""
        query = 'ExecutionStatus="Running"'
        if wf_type:
            query += f' AND WorkflowType="{wf_type}"'
        result = await self._client.count_workflows(query)
        return result.count

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

        # Only scan workflow types that have human tasks registered
        from core.workflows import get_all_workflows
        human_wf_types = {
            wf.workflow_cls.__name__
            for wf in get_all_workflows()
            if wf.task_types  # Only workflows with human task types
        }

        # Collect candidate workflow IDs first (fast — just listing)
        candidates: list[tuple] = []  # (wf_id, wf_type, start_time)
        async for wf in self._client.list_workflows(query, page_size=100):
            if wf.workflow_type not in human_wf_types:
                continue
            candidates.append((wf.id, wf.workflow_type, wf.start_time))
            if len(candidates) >= 200:  # Safety cap
                break

        # Query candidates for pending tasks in parallel batches
        batch_size = 20
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]

            async def _check(wf_id, wf_type, start_time):
                try:
                    meta = await self.get_pending_task(wf_id)
                    if not meta:
                        return None

                    if search:
                        haystack = f"{wf_id} {meta.title} {meta.description} {wf_type or ''}".lower()
                        if search.lower() not in haystack:
                            return None

                    if not is_admin:
                        if not is_assigned_to_user(
                            meta.assigned_user, meta.assigned_group,
                            user_slug, user_group_slugs or [],
                        ):
                            return None

                    if assignment == "mine":
                        if not meta.assigned_user or meta.assigned_user != user_slug:
                            return None
                    elif assignment == "my_groups":
                        if not meta.assigned_group or meta.assigned_group not in (user_group_slugs or []):
                            return None
                    elif assignment == "unassigned":
                        if meta.assigned_user or meta.assigned_group:
                            return None

                    return PendingTaskItem(
                        workflow_id=wf_id,
                        workflow_type=wf_type,
                        task_type=meta.task_type,
                        title=meta.title,
                        description=meta.description,
                        started=relative_time(start_time),
                        assigned_user=meta.assigned_user,
                        assigned_group=meta.assigned_group,
                    )
                except Exception:
                    return None

            results = await asyncio.gather(*[_check(wid, wt, st) for wid, wt, st in batch])
            all_pending.extend(r for r in results if r is not None)

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
        grouped = group_by_parent(items[:size])
        return PaginatedResult(items=grouped, has_next=has_next)
