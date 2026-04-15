import os

from pydantic import BaseModel


class AppSettings(BaseModel):
    temporal_address: str = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    page_size: int = 20
    task_queue: str = "hello-world-task-queue"


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
