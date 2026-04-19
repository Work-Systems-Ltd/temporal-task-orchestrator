import asyncio

from temporalio import workflow

from core.workflows import WorkSysFlow, register_workflow
from tasks.human.approval import ApprovalTask
from tasks.human.approval_input import ApprovalInputTask
from tasks.human.hiring_input import HiringInputTask
from tasks.human.onboarding import OnboardingTask
from tasks.human.onboarding_input import OnboardingInputTask
from workflows.approval import ApprovalWorkflow
from workflows.onboarding import OnboardingWorkflow


@register_workflow(
    key="hiring",
    label="Hiring Pipeline",
    description="Full hiring flow: approval then onboarding",
    task_types=[ApprovalTask, OnboardingTask],
    required_users=["admin"],
    required_groups=["admin"],
)
@workflow.defn
class HiringWorkflow(WorkSysFlow):
    """Orchestrates a full hiring pipeline: approval then onboarding."""

    input_task = HiringInputTask

    @workflow.run
    async def run(self, input: HiringInputTask.Model) -> str:
        # Step 1: Get hiring approved via child workflow
        approval_result = await workflow.execute_child_workflow(
            ApprovalWorkflow.run,
            ApprovalInputTask.Model(
                description=f"New hire request: {input.employee_name}",
                urgency=input.urgency,
            ),
            id=f"{workflow.info().workflow_id}-approval",
        )

        if "REJECTED" in approval_result:
            return f"Hiring rejected: {approval_result}"

        # Step 2: Collect onboarding details via human task
        onboarding_data = await self.create_human_task(
            OnboardingInputTask,
            title="Provide onboarding details",
            description=f"The hire for {input.employee_name} has been approved. Please provide onboarding details.",
            assigned_group="admin",
        )
        onboarding_input = OnboardingInputTask.Model(**onboarding_data)

        # Step 3: Run onboarding workflows concurrently
        onboarding1 = await workflow.start_child_workflow(
            OnboardingWorkflow.run,
            onboarding_input,
            id=f"{workflow.info().workflow_id}-onboarding",
        )

        onboarding2 = await workflow.start_child_workflow(
            OnboardingWorkflow.run,
            onboarding_input,
            id=f"{workflow.info().workflow_id}-onboarding-2",
        )

        result1, result2 = await asyncio.gather(onboarding1, onboarding2)

        return f"Hiring complete for {input.employee_name}: {result1} | {result2}"
