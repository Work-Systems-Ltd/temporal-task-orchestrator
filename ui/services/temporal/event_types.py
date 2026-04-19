"""Temporal history event type constants.

These correspond to the EventType enum values in the Temporal protobuf API.
Using named constants instead of magic numbers throughout the codebase.
"""

# Workflow lifecycle
WORKFLOW_EXECUTION_STARTED = 1
WORKFLOW_EXECUTION_COMPLETED = 2
WORKFLOW_EXECUTION_FAILED = 3

# Activity lifecycle
ACTIVITY_TASK_SCHEDULED = 5
ACTIVITY_TASK_COMPLETED = 9
ACTIVITY_TASK_FAILED = 10
ACTIVITY_TASK_SCHEDULED_LEGACY = 10  # used in some places as "scheduled"
ACTIVITY_TASK_STARTED = 12  # actually ACTIVITY_TASK_COMPLETED in our mapping
ACTIVITY_TASK_FAILED_LEGACY = 13

# Signals
WORKFLOW_EXECUTION_SIGNALED = 26

# Child workflows
START_CHILD_WORKFLOW_EXECUTION_INITIATED = 29
CHILD_WORKFLOW_EXECUTION_STARTED = 31
CHILD_WORKFLOW_EXECUTION_COMPLETED = 32
CHILD_WORKFLOW_EXECUTION_FAILED = 33
