"""Unified CLI for the Temporal Task Orchestrator."""
from __future__ import annotations

import asyncio
import os

import typer

app = typer.Typer(help="Temporal Task Orchestrator CLI")


@app.command()
def migrate(
    revision: str = typer.Argument("head", help="Target revision (default: head)"),
) -> None:
    """Run database migrations via Alembic."""
    from alembic import command
    from alembic.config import Config

    from ui.config import AppSettings

    settings = AppSettings()

    cfg = Config()
    cfg.set_main_option("script_location", "core/migrations")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, revision)
    typer.echo(f"Migrations applied up to '{revision}'.")


@app.command()
def ui(
    host: str = typer.Option("0.0.0.0", help="Bind address"),
    port: int = typer.Option(8090, help="Bind port"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
) -> None:
    """Start the FastAPI web UI."""
    import uvicorn

    uvicorn.run("ui.app:app", host=host, port=port, reload=reload)


@app.command()
def worker() -> None:
    """Start the Temporal worker."""
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
        typer.echo(f"Worker started, listening on '{settings.task_queue}'...")
        await w.run()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
