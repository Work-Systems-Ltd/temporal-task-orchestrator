from temporalio import workflow

from core.workflows import WorkSysFlow, register_workflow
from tasks.human.approval import ApprovalTask
from tasks.human.approval_input import ApprovalInputTask
from tasks.system.approval import log_request, process_approval, process_rejection


@register_workflow(
    key="approval",
    label="Approval",
    description="Submit a request that requires human approval or rejection",
    task_types=[ApprovalTask],
    required_groups=["admin"],
)
@workflow.defn
class ApprovalWorkflow(WorkSysFlow):
    input_task = ApprovalInputTask

    @workflow.run
    async def run(self, input: ApprovalInputTask.Model) -> str:
        await self.create_system_task(log_request, input.description)

        human_data = await self.create_human_task(
            ApprovalTask,
            title=f"Approve: {input.description}",
            description=f"Please review this {input.urgency}-priority request and approve or reject it.",
            assigned_group="admin",
        )

        decision = human_data["decision"]
        comment = human_data.get("comment", "")

        if decision == "approve":
            result = await self.create_system_task(process_approval, input.description, comment)
        else:
            result = await self.create_system_task(process_rejection, input.description, comment)

        return result
