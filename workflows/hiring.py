from datetime import timedelta

from temporalio import workflow

from core.models import TaskMeta
from core.workflows import WorkSysFlow
from tasks.approval_input import ApprovalInputTask
from tasks.hiring_input import HiringInputTask
from tasks.onboarding_input import OnboardingInputTask
from workflows.approval import ApprovalWorkflow
from workflows.onboarding import OnboardingWorkflow


@workflow.defn
class HiringWorkflow(WorkSysFlow):
    """Orchestrates a full hiring pipeline: approval then onboarding."""

    @workflow.run
    async def run(self, input: HiringInputTask.Model) -> str:
        # Step 1: Get hiring approved
        approval_result = await workflow.execute_child_workflow(
            ApprovalWorkflow.run,
            ApprovalInputTask.Model(
                description="New hire request",
                urgency=input.urgency,
            ),
            id=f"{workflow.info().workflow_id}-approval",
        )

        if "REJECTED" in approval_result:
            return f"Hiring rejected: {approval_result}"

        # Step 2: Collect onboarding details
        onboarding_meta = TaskMeta(
            task_type="onboarding_input",
            title="Provide onboarding details",
            description="The hire has been approved. Please provide the new employee's details.",
        )
        onboarding_data = await self.wait_for_human_task(onboarding_meta)
        onboarding_input = OnboardingInputTask.Model(**onboarding_data)

        # Step 3: Run onboarding
        onboarding_result = await workflow.execute_child_workflow(
            OnboardingWorkflow.run,
            onboarding_input,
            id=f"{workflow.info().workflow_id}-onboarding",
        )

        return f"Hiring complete for {onboarding_input.employee_name}: {onboarding_result}"
