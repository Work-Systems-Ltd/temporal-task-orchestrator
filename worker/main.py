"""Temporal worker process."""
from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from workflows.approval import (
    ApprovalWorkflow,
    log_request,
    process_approval,
    process_rejection,
)
from workflows.hiring import HiringWorkflow
from workflows.onboarding import (
    OnboardingWorkflow,
    create_onboarding_ticket,
    provision_equipment,
    setup_accounts,
)

import tasks  # noqa: F401 — trigger task registration
from core.workflows import validate_registrations
from ui.config import AppSettings


def run() -> None:
    """Start the Temporal worker."""
    validate_registrations()
    settings = AppSettings()

    async def _run() -> None:
        client = await Client.connect(settings.temporal_address)
        w = Worker(
            client,
            task_queue=settings.task_queue,
            workflows=[ApprovalWorkflow, HiringWorkflow, OnboardingWorkflow],
            activities=[
                log_request,
                process_approval,
                process_rejection,
                create_onboarding_ticket,
                provision_equipment,
                setup_accounts,
            ],
        )
        print(f"Worker started, listening on '{settings.task_queue}'...")
        await w.run()

    asyncio.run(_run())
