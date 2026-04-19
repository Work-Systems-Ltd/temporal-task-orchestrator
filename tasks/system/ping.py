from pydantic import BaseModel

from core.tasks import SystemTask, register_task


@register_task
class PingTask(SystemTask):
    task_type = "ping"
    label = "Ping"

    class Model(BaseModel):
        message: str

    @staticmethod
    async def run(message: str) -> str:
        print(f"[Ping] {message}")
        return f"pong: {message}"
