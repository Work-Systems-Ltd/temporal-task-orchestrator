"""Mixin for workflow detail, timeline, and run history."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ui.helpers import duration, relative_time, status_name
from ui.models import TimelineEvent, TimelineStats, WorkflowDetail
from ui.services.temporal.helpers import ms_duration
from ui.services.temporal.event_types import (
    WORKFLOW_EXECUTION_STARTED, WORKFLOW_EXECUTION_COMPLETED, WORKFLOW_EXECUTION_FAILED,
    ACTIVITY_TASK_SCHEDULED_V2 as ACTIVITY_TASK_SCHEDULED,
    ACTIVITY_TASK_COMPLETED_V2 as ACTIVITY_TASK_COMPLETED,
    ACTIVITY_TASK_FAILED_V2 as ACTIVITY_TASK_FAILED,
    WORKFLOW_EXECUTION_SIGNALED,
    START_CHILD_WORKFLOW_EXECUTION_INITIATED, CHILD_WORKFLOW_EXECUTION_STARTED,
    CHILD_WORKFLOW_EXECUTION_COMPLETED, CHILD_WORKFLOW_EXECUTION_FAILED,
)

logger = logging.getLogger(__name__)


class DetailMixin:
    """Workflow detail, timeline events, and run history."""

    async def get_workflow_detail(
        self, workflow_id: str, run_id: str | None = None,
    ) -> WorkflowDetail | None:
        """Fetch the detail summary for a single workflow execution."""
        try:
            handle = self._client.get_workflow_handle(workflow_id, run_id=run_id)
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
        except Exception as exc:
            logger.debug("Workflow detail error: %s", exc)
            return None

    async def get_run_history(self, workflow_id: str) -> list[dict]:
        """Return all runs for a workflow ID, newest first."""
        runs: list[dict] = []
        query = f'WorkflowId="{workflow_id}"'
        async for wf in self._client.list_workflows(query):
            runs.append({
                "run_id": wf.run_id or "",
                "status": status_name(wf.status),
                "started": relative_time(wf.start_time),
                "duration": duration(wf.start_time, wf.close_time),
            })
        return runs

    async def get_workflow_timeline(
        self, workflow_id: str, run_id: str | None = None,
    ) -> tuple[list[TimelineEvent], TimelineStats]:
        """Build the timeline events and stats for a workflow execution."""
        handle = self._client.get_workflow_handle(workflow_id, run_id=run_id)
        history = await handle.fetch_history()

        scheduled_activities: dict[int, tuple[str, datetime]] = {}
        child_workflows: dict[int, tuple[str, str]] = {}
        events: list[TimelineEvent] = []

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
            if etype == WORKFLOW_EXECUTION_STARTED:  # WORKFLOW_EXECUTION_STARTED
                workflow_start = _ts(event)
                attrs = event.workflow_execution_started_event_attributes
                if attrs and attrs.input and attrs.input.payloads:
                    try:
                        workflow_input = attrs.input.payloads[0].data.decode("utf-8")
                    except Exception as exc:
                        logger.debug("Failed to decode workflow payload: %s", exc)
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow started", status="completed"))

            elif etype == WORKFLOW_EXECUTION_COMPLETED:  # WORKFLOW_EXECUTION_COMPLETED
                workflow_end = _ts(event)
                attrs = event.workflow_execution_completed_event_attributes
                if attrs and attrs.result and attrs.result.payloads:
                    try:
                        workflow_output = attrs.result.payloads[0].data.decode("utf-8")
                    except Exception as exc:
                        logger.debug("Failed to decode workflow payload: %s", exc)
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow completed", status="completed"))

            elif etype == WORKFLOW_EXECUTION_FAILED:  # WORKFLOW_EXECUTION_FAILED
                workflow_end = _ts(event)
                fail_detail = ""
                attrs = event.workflow_execution_failed_event_attributes
                if attrs and attrs.failure:
                    fail_detail = attrs.failure.message or ""
                    if attrs.failure.cause and attrs.failure.cause.message:
                        fail_detail = attrs.failure.cause.message
                events.append(TimelineEvent(event_id=eid, event_time=etime, label="Workflow failed", status="failed", detail=fail_detail))

            # Activity lifecycle
            elif etype == ACTIVITY_TASK_SCHEDULED:  # ACTIVITY_TASK_SCHEDULED
                attrs = event.activity_task_scheduled_event_attributes
                name = attrs.activity_type.name if attrs and attrs.activity_type else "unknown"
                scheduled_activities[eid] = (name, _ts(event))

            elif etype == ACTIVITY_TASK_COMPLETED:  # ACTIVITY_TASK_COMPLETED
                attrs = event.activity_task_completed_event_attributes
                sched_id = attrs.scheduled_event_id if attrs else 0
                name, sched_time = scheduled_activities.get(sched_id, ("activity", _ts(event)))
                act_duration = (_ts(event) - sched_time).total_seconds()
                total_activity_secs += act_duration
                last_activity_end = _ts(event)
                dur_str = ms_duration(sched_time, _ts(event))
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=name, status="completed", duration=dur_str, kind="system"))

            elif etype == ACTIVITY_TASK_FAILED:  # ACTIVITY_TASK_FAILED
                attrs = event.activity_task_failed_event_attributes
                sched_id = attrs.scheduled_event_id if attrs else 0
                name, sched_time = scheduled_activities.get(sched_id, ("activity", _ts(event)))
                act_duration = (_ts(event) - sched_time).total_seconds()
                total_activity_secs += act_duration
                dur_str = ms_duration(sched_time, _ts(event))
                fail_detail = ""
                if attrs and attrs.failure:
                    fail_detail = attrs.failure.message or ""
                    if attrs.failure.cause and attrs.failure.cause.message:
                        fail_detail = attrs.failure.cause.message
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=name, status="failed", detail=fail_detail, duration=dur_str, kind="system"))

            # Signals
            elif etype == WORKFLOW_EXECUTION_SIGNALED:  # WORKFLOW_EXECUTION_SIGNALED
                attrs = event.workflow_execution_signaled_event_attributes
                sig_name = attrs.signal_name if attrs else "signal"
                dur_str = ""
                if last_activity_end:
                    wait = (_ts(event) - last_activity_end).total_seconds()
                    total_wait_secs += wait
                    dur_str = ms_duration(last_activity_end, _ts(event))

                # Extract signal payload for human task completions
                input_data = ""
                is_human = sig_name == "complete_human_task"
                if is_human and attrs and attrs.input and attrs.input.payloads:
                    try:
                        input_data = attrs.input.payloads[0].data.decode("utf-8")
                    except Exception:
                        pass

                events.append(TimelineEvent(
                    event_id=eid,
                    event_time=etime,
                    label="Task completed" if is_human else f"Signal: {sig_name}",
                    status="completed" if is_human else "info",
                    duration=dur_str,
                    kind="human" if is_human else "signal",
                    input_data=input_data,
                ))

            # Child workflows
            elif etype == START_CHILD_WORKFLOW_EXECUTION_INITIATED:  # START_CHILD_WORKFLOW_EXECUTION_INITIATED
                attrs = event.start_child_workflow_execution_initiated_event_attributes
                wf_type = attrs.workflow_type.name if attrs and attrs.workflow_type else "child"
                child_wf_id = attrs.workflow_id if attrs else ""
                child_workflows[eid] = (wf_type, child_wf_id)

            elif etype == CHILD_WORKFLOW_EXECUTION_STARTED:  # CHILD_WORKFLOW_EXECUTION_STARTED
                attrs = event.child_workflow_execution_started_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                wf_type, child_wf_id = child_workflows.get(init_id, ("child", ""))
                if not child_wf_id and attrs and attrs.workflow_execution:
                    child_wf_id = attrs.workflow_execution.workflow_id
                link = f"/workflow/{child_wf_id}" if child_wf_id else ""
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=wf_type, status="info", detail="Child workflow", link=link, kind="workflow"))

            elif etype == CHILD_WORKFLOW_EXECUTION_COMPLETED:  # CHILD_WORKFLOW_EXECUTION_COMPLETED
                attrs = event.child_workflow_execution_completed_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                wf_type, child_wf_id = child_workflows.get(init_id, ("child", ""))
                link = f"/workflow/{child_wf_id}" if child_wf_id else ""
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=wf_type, status="completed", detail="Child completed", link=link, kind="workflow"))

            elif etype == CHILD_WORKFLOW_EXECUTION_FAILED:  # CHILD_WORKFLOW_EXECUTION_FAILED
                attrs = event.child_workflow_execution_failed_event_attributes
                init_id = attrs.initiated_event_id if attrs else 0
                wf_type, child_wf_id = child_workflows.get(init_id, ("child", ""))
                link = f"/workflow/{child_wf_id}" if child_wf_id else ""
                fail_detail = "Child failed"
                if attrs and attrs.failure:
                    msg = attrs.failure.message or ""
                    if attrs.failure.cause and attrs.failure.cause.message:
                        msg = attrs.failure.cause.message
                    if msg:
                        fail_detail = msg
                events.append(TimelineEvent(event_id=eid, event_time=etime, label=wf_type, status="failed", detail=fail_detail, link=link))

        _epoch = datetime.min.replace(tzinfo=timezone.utc)
        stats = TimelineStats(
            activity_time=ms_duration(_epoch, _epoch + timedelta(seconds=total_activity_secs)) if total_activity_secs > 0 else "—",
            wait_time=ms_duration(_epoch, _epoch + timedelta(seconds=total_wait_secs)) if total_wait_secs > 0 else "—",
            total_time=ms_duration(workflow_start, workflow_end) if workflow_start and workflow_end else "—",
            workflow_input=workflow_input,
            workflow_output=workflow_output,
        )

        return events, stats
