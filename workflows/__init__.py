from core.workflows import register_workflow
from tasks.human.approval import ApprovalTask
from tasks.human.approval_input import ApprovalInputTask
from tasks.human.hiring_input import HiringInputTask
from tasks.human.onboarding import OnboardingTask
from tasks.human.onboarding_input import OnboardingInputTask
from tasks.human.testing_input import TestingInputTask
from workflows.approval import ApprovalWorkflow
from workflows.hiring import HiringWorkflow
from workflows.onboarding import OnboardingWorkflow
from workflows.ping import PingWorkflow
from workflows.testing import TestingWorkflow

register_workflow(
    key="approval",
    label="Approval",
    description="Submit a request that requires human approval or rejection",
    workflow_cls=ApprovalWorkflow,
    input_label="Request description",
    input_placeholder="e.g. Expense report: $500 for conference travel",
    input_task=ApprovalInputTask,
    task_types=[ApprovalTask],
    required_groups=[],
)

register_workflow(
    key="onboarding",
    label="Employee Onboarding",
    description="Start the onboarding process for a new team member",
    workflow_cls=OnboardingWorkflow,
    input_label="Employee name",
    input_placeholder="e.g. Jane Smith",
    input_task=OnboardingInputTask,
    task_types=[OnboardingTask],
    required_users=["admin"],
)

register_workflow(
    key="ping",
    label="Ping",
    description="Simple test — runs one system task and returns the result",
    workflow_cls=PingWorkflow,
    input_label="Message",
    input_placeholder="e.g. hello",
    task_types=[],
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
    task_types=[ApprovalTask, OnboardingTask],
    required_users=["admin"],
    required_groups=["admin"],
)
