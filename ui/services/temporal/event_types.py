"""Temporal history event type constants.

These correspond to the EventType enum values in the Temporal protobuf API.
Using named constants instead of magic numbers throughout the codebase.

Note: detail.py and graph.py historically used different numbering for
activity events. The constants below match what each file originally used.
"""

# Workflow lifecycle
WORKFLOW_EXECUTION_STARTED = 1
WORKFLOW_EXECUTION_COMPLETED = 2
WORKFLOW_EXECUTION_FAILED = 3

# Activity lifecycle (as used in graph.py — proto enum values)
ACTIVITY_TASK_SCHEDULED = 5
ACTIVITY_TASK_COMPLETED = 9
ACTIVITY_TASK_FAILED = 10

# Activity lifecycle (as used in detail.py — different numbering)
ACTIVITY_TASK_SCHEDULED_V2 = 10
ACTIVITY_TASK_COMPLETED_V2 = 12
ACTIVITY_TASK_FAILED_V2 = 13

# Signals
WORKFLOW_EXECUTION_SIGNALED = 26

# Child workflows
START_CHILD_WORKFLOW_EXECUTION_INITIATED = 29
CHILD_WORKFLOW_EXECUTION_STARTED = 31
CHILD_WORKFLOW_EXECUTION_COMPLETED = 32
CHILD_WORKFLOW_EXECUTION_FAILED = 33
