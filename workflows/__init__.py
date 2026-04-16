from core.workflows import register_workflow
from tasks.approval_input import ApprovalInputTask
from tasks.hiring_input import HiringInputTask
from tasks.onboarding_input import OnboardingInputTask
from workflows.approval import ApprovalWorkflow
from workflows.hiring import HiringWorkflow
from workflows.onboarding import OnboardingWorkflow

register_workflow(
    key="approval",
    label="Approval",
    description="Submit a request that requires human approval or rejection",
    workflow_cls=ApprovalWorkflow,
    input_label="Request description",
    input_placeholder="e.g. Expense report: $500 for conference travel",
    input_task=ApprovalInputTask,
    task_types=["approval"],
)

register_workflow(
    key="onboarding",
    label="Employee Onboarding",
    description="Start the onboarding process for a new team member",
    workflow_cls=OnboardingWorkflow,
    input_label="Employee name",
    input_placeholder="e.g. Jane Smith",
    input_task=OnboardingInputTask,
    task_types=["onboarding"],
)

register_workflow(
    key="hiring",
    label="Hiring Pipeline",
    description="Full hiring flow: approval then onboarding",
    workflow_cls=HiringWorkflow,
    input_label="Employee details",
    input_placeholder="",
    input_task=HiringInputTask,
    task_types=["approval", "onboarding"],
)
