from datetime import timedelta

from temporalio import workflow

from core.workflows import WorkSysFlow
from tasks.human.approval import ApprovalTask
from tasks.human.approval_input import ApprovalInputTask
from tasks.system.approval import log_request, process_approval, process_rejection


@workflow.defn
class ApprovalWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, input: ApprovalInputTask.Model) -> str:
        await workflow.execute_activity(
            log_request,
            input.description,
            start_to_close_timeout=timedelta(seconds=10),
        )

        human_data = await self.wait_for_task(
            ApprovalTask,
            title=f"Approve: {input.description}",
            description=f"Please review this {input.urgency}-priority request and approve or reject it.",
            assigned_group="admin",
        )

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
