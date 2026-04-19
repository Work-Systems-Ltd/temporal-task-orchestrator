"""Temporal worker process."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from temporalio.client import Client
from temporalio.worker import Worker

import tasks  # noqa: F401 — trigger task registration
import workflows  # noqa: F401 — trigger workflow registration
from core.activities import TaskPersistenceActivities
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
        # Database connection for task persistence activities
        engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=10)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        persistence = TaskPersistenceActivities(session_factory=session_factory)

        client = await Client.connect(settings.temporal_address)

        # Combine user-defined activities with infrastructure activities
        all_activities = get_all_activities() + [
            persistence.create_task_record,
            persistence.complete_task_record,
            persistence.update_task_record,
            persistence.cancel_task_record,
        ]

        w = Worker(
            client,
            task_queue=settings.task_queue,
            workflows=workflow_classes,
            activities=all_activities,
        )
        logger.info("Worker started, listening on '%s'...", settings.task_queue)
        try:
            await w.run()
        finally:
            await engine.dispose()

    asyncio.run(_run())
