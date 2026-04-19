"""Temporal worker process."""
from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

import tasks  # noqa: F401 — trigger task registration
import workflows  # noqa: F401 — trigger workflow registration
from core.tasks.registry import get_all_activities
from core.workflows import get_all_workflows, validate_registrations
from ui.config import AppSettings

logger = logging.getLogger(__name__)


def run() -> None:
    """Start the Temporal worker."""
    validate_registrations()
    settings = AppSettings()

    workflow_classes = [wf.workflow_cls for wf in get_all_workflows()]

    async def _run() -> None:
        client = await Client.connect(settings.temporal_address)
        w = Worker(
            client,
            task_queue=settings.task_queue,
            workflows=workflow_classes,
            activities=get_all_activities(),
        )
        logger.info("Worker started, listening on '%s'...", settings.task_queue)
        await w.run()

    asyncio.run(_run())
