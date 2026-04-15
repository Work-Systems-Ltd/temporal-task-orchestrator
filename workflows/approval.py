import json
from datetime import timedelta

from temporalio import activity, workflow


@activity.defn
async def log_request(request: str) -> str:
    print(f"[ApprovalWorkflow] New request logged: {request}")
    return f"Request logged: {request}"


@activity.defn
async def process_approval(request: str, comment: str) -> str:
    msg = f"[ApprovalWorkflow] APPROVED: {request}"
    if comment:
        msg += f" (comment: {comment})"
    print(msg)
    return msg


@activity.defn
async def process_rejection(request: str, comment: str) -> str:
    msg = f"[ApprovalWorkflow] REJECTED: {request}"
    if comment:
        msg += f" (reason: {comment})"
    print(msg)
    return msg


@workflow.defn
class ApprovalWorkflow:
    def __init__(self):
        self._human_task_complete = False
        self._human_task_data: dict | None = None
        self._pending_task: dict | None = None

    @workflow.signal
    async def complete_human_task(self, data: str) -> None:
        self._human_task_data = json.loads(data)
        self._human_task_complete = True

    @workflow.query
    def get_pending_task(self) -> str:
        if self._pending_task:
            return json.dumps(self._pending_task)
        return ""

    @workflow.run
    async def run(self, request: str) -> str:
        await workflow.execute_activity(
            log_request,
            request,
            start_to_close_timeout=timedelta(seconds=10),
        )

        self._pending_task = {
            "task_type": "approval",
            "title": f"Approve: {request}",
            "description": "Please review this request and approve or reject it.",
        }

        await workflow.wait_condition(lambda: self._human_task_complete)

        self._pending_task = None
        decision = self._human_task_data["decision"]
        comment = self._human_task_data.get("comment", "")

        if decision == "approve":
            result = await workflow.execute_activity(
                process_approval,
                args=[request, comment],
                start_to_close_timeout=timedelta(seconds=10),
            )
        else:
            result = await workflow.execute_activity(
                process_rejection,
                args=[request, comment],
                start_to_close_timeout=timedelta(seconds=10),
            )

        return result
