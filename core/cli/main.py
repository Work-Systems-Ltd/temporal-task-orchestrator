"""Unified CLI for the Temporal Task Orchestrator."""
from __future__ import annotations

import sys

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
    import subprocess

    cmd = [
        sys.executable, "-m", "uvicorn", "ui.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")
    raise SystemExit(subprocess.call(cmd))


@app.command()
def worker() -> None:
    """Start the Temporal worker."""
    from worker import run

    run()


if __name__ == "__main__":
    app()
