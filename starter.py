import asyncio
import os
import uuid

from temporalio.client import Client

from workflows.approval import ApprovalWorkflow


async def main():
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_address)

    approval_id = f"approval-{uuid.uuid4().hex[:8]}"
    await client.start_workflow(
        ApprovalWorkflow.run,
        "Expense report: $500 for conference travel",
        id=approval_id,
        task_queue="hello-world-task-queue",
    )
    print(f"Approval workflow started (waiting for human input)")
    print(f"  Workflow ID: {approval_id}")
    print(f"  Open http://localhost:8090 to approve or reject")


if __name__ == "__main__":
    asyncio.run(main())
