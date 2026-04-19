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
    seed_groups: str = ""


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
