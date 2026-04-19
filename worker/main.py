"""Temporal worker process."""
from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from workflows.approval import ApprovalWorkflow
from workflows.hiring import HiringWorkflow
from workflows.onboarding import OnboardingWorkflow
from workflows.ping import PingWorkflow
from workflows.testing import TestingWorkflow

import tasks  # noqa: F401 — trigger task registration
from core.tasks.registry import get_all_activities
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
            workflows=[ApprovalWorkflow, HiringWorkflow, OnboardingWorkflow, PingWorkflow, TestingWorkflow],
            activities=get_all_activities(),
        )
        print(f"Worker started, listening on '{settings.task_queue}'...")
        await w.run()

    asyncio.run(_run())
