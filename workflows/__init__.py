from core.workflows import register_workflow
from tasks.approval_input import ApprovalInputTask
from tasks.hiring_input import HiringInputTask
from tasks.onboarding_input import OnboardingInputTask
from tasks.testing_input import TestingInputTask
from workflows.approval import ApprovalWorkflow
from workflows.hiring import HiringWorkflow
from workflows.onboarding import OnboardingWorkflow
from workflows.testing import TestingWorkflow

register_workflow(
    key="approval",
    label="Approval",
    description="Submit a request that requires human approval or rejection",
    workflow_cls=ApprovalWorkflow,
    input_label="Request description",
    input_placeholder="e.g. Expense report: $500 for conference travel",
    input_task=ApprovalInputTask,
    task_types=["approval"],
    required_groups=["admin"],
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
    required_users=["admin"],
)

register_workflow(
    key="testing",
    label="Testing",
    description="Configurable test workflow — can succeed or fail at a chosen step",
    workflow_cls=TestingWorkflow,
    input_label="Test message",
    input_placeholder="e.g. Test run #1",
    input_task=TestingInputTask,
    task_types=[],
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
    required_users=["admin"],
    required_groups=["admin"],
)
