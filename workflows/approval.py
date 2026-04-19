from temporalio import workflow

from core.workflows import WorkSysFlow
from tasks.human.approval import ApprovalTask
from tasks.human.approval_input import ApprovalInputTask
from tasks.system.approval import LogRequestTask, ProcessApprovalTask, ProcessRejectionTask


@workflow.defn
class ApprovalWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, input: ApprovalInputTask.Model) -> str:
        await self.create_system_task(LogRequestTask, input.description)

        human_data = await self.wait_for_task(
            ApprovalTask,
            title=f"Approve: {input.description}",
            description=f"Please review this {input.urgency}-priority request and approve or reject it.",
            assigned_group="admin",
        )

        decision = human_data["decision"]
        comment = human_data.get("comment", "")

        if decision == "approve":
            result = await self.create_system_task(ProcessApprovalTask, input.description, comment)
        else:
            result = await self.create_system_task(ProcessRejectionTask, input.description, comment)

        return result
