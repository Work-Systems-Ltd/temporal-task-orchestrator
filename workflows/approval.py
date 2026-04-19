from datetime import timedelta

from temporalio import activity, workflow

from core.workflows import WorkSysFlow
from tasks.approval_input import ApprovalInputTask


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
class ApprovalWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, input: ApprovalInputTask.Model) -> str:
        await workflow.execute_activity(
            log_request,
            input.description,
            start_to_close_timeout=timedelta(seconds=10),
        )

        task_meta = TaskMeta(
            task_type="approval",
            title=f"Approve: {input.description}",
            description=f"Please review this {input.urgency}-priority request and approve or reject it.",
        )
        human_data = await self.wait_for_human_task(task_meta)

        decision = human_data["decision"]
        comment = human_data.get("comment", "")

        if decision == "approve":
            result = await workflow.execute_activity(
                process_approval,
                args=[input.description, comment],
                start_to_close_timeout=timedelta(seconds=10),
            )
        else:
            result = await workflow.execute_activity(
                process_rejection,
                args=[input.description, comment],
                start_to_close_timeout=timedelta(seconds=10),
            )

        return result
