from pydantic import BaseModel
from temporalio import activity

from core.tasks import SystemTask, register_task

import subprocess

@activity.defn
async def ping(ip_address: str) -> str:
    # Use the system's ping command to ping the specified IP address and return the raw result
    # result = subprocess.run(
    #     ["ping", "-c", "4", ip_address], 
    #     capture_output=True, 
    #     text=True, 
    #     timeout=30
    # )
    # # Return both stdout and stderr for complete output
    # output = result.stdout
    # if result.stderr:
    #     output += f"\nErrors:\n{result.stderr}"
    return "PONG"



@register_task
class PingTask(SystemTask):
    task_type = "ping"
    label = "Ping"
    _activity_fn = ping

    class Model(BaseModel):
        message: str
