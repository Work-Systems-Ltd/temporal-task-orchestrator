from workflows.approval import ApprovalWorkflow
from workflows.onboarding import OnboardingWorkflow
from workflows.registry import register_workflow

register_workflow(
    key="approval",
    label="Approval",
    description="Submit a request that requires human approval or rejection",
    workflow_cls=ApprovalWorkflow,
    input_label="Request description",
    input_placeholder="e.g. Expense report: $500 for conference travel",
)

register_workflow(
    key="onboarding",
    label="Employee Onboarding",
    description="Start the onboarding process for a new team member",
    workflow_cls=OnboardingWorkflow,
    input_label="Employee name",
    input_placeholder="e.g. Jane Smith",
)
