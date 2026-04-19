from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    temporal_address: str = "localhost:7233"
    page_size: int = 20
    task_queue: str = "hello-world-task-queue"
    database_url: str = "postgresql+asyncpg://temporal:temporal@localhost:5432/taskapp"
    session_secret: str = "insecure-dev-secret-change-me"
    seed_username: str = ""
    seed_password: str = ""
    seed_groups: str = "admin"
    admin_group: str = "admin"


STATUS_QUERIES: dict[str, str | None] = {
    "pending": 'ExecutionStatus="Running"',
    "running": 'ExecutionStatus="Running"',
    "completed": 'ExecutionStatus="Completed"',
    "failed": 'ExecutionStatus="Failed"',
    "cancelled": 'ExecutionStatus="Canceled"',
    "terminated": 'ExecutionStatus="Terminated"',
    "timed_out": 'ExecutionStatus="TimedOut"',
    "all": None,
}

TAB_ORDER: list[str] = ["pending", "running", "completed", "failed", "all"]
WORKFLOW_TAB_ORDER: list[str] = ["running", "completed", "failed", "all"]

# Task (DB-persisted) status configuration
TASK_TAB_ORDER: list[str] = ["open", "in_progress", "on_hold", "completed", "cancelled", "all"]
TASK_TAB_LABELS: dict[str, str] = {
    "open": "Open",
    "in_progress": "In Progress",
    "on_hold": "On Hold",
    "completed": "Completed",
    "cancelled": "Cancelled",
    "all": "All",
}
TASK_PRIORITY_ORDER: list[str] = ["critical", "high", "medium", "low"]
TASK_SORT_OPTIONS: list[dict[str, str]] = [
    {"value": "created_at:desc", "label": "Newest first"},
    {"value": "created_at:asc", "label": "Oldest first"},
    {"value": "priority:asc", "label": "Priority (high to low)"},
    {"value": "updated_at:desc", "label": "Recently updated"},
]
