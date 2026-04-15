import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from workflows.approval import (
    ApprovalWorkflow,
    log_request,
    process_approval,
    process_rejection,
)
from workflows.onboarding import (
    OnboardingWorkflow,
    create_onboarding_ticket,
    provision_equipment,
    setup_accounts,
)


async def main():
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_address)
    worker = Worker(
        client,
        task_queue="hello-world-task-queue",
        workflows=[ApprovalWorkflow, OnboardingWorkflow],
        activities=[
            log_request,
            process_approval,
            process_rejection,
            create_onboarding_ticket,
            provision_equipment,
            setup_accounts,
        ],
    )
    print("Worker started, listening on 'hello-world-task-queue'...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
