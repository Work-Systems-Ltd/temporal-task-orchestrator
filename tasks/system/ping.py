from pydantic import BaseModel
from temporalio import activity

from core.tasks import SystemTask, register_task


@activity.defn
async def ping(message: str) -> str:
    print(f"[Ping] {message}")
    return f"pong: {message}"


@register_task
class PingTask(SystemTask):
    task_type = "ping"
    label = "Ping"
    _activity_fn = ping

    class Model(BaseModel):
        message: str
