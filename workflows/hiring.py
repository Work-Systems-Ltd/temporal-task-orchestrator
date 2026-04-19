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

        self.create_human_task(
            lambda: None,  # No activity, just a signal wait
            task_type="hiring",
            title="Hiring approved",
            description="The new hire request has been approved. Please proceed with onboarding.",
        )

        # Step 3: Run onboarding
        import asyncio
        # Start both child workflows concurrently
        onboarding1 = await workflow.start_child_workflow(
            OnboardingWorkflow.run,
            lambda: None,  # No input needed, just a signal wait
            id=f"{workflow.info().workflow_id}-onboarding",
        )

        onboarding2 = await workflow.start_child_workflow(
            OnboardingWorkflow.run,
            lambda: None,   # No input needed, just a signal wait
            id=f"{workflow.info().workflow_id}-onboarding-test",
        )

        # Now wait for both results
        result1, result2 = await asyncio.gather(
            onboarding1,
            onboarding2,
        )

        return "foo"
        #return f"Hiring complete for {onboarding_input.employee_name}: {onboarding_result}"
