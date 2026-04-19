from pydantic import BaseModel
from temporalio import activity

from core.tasks import SystemTask, register_task


@activity.defn
async def log_request(request: str) -> str:
    print(f"[ApprovalWorkflow] New request logged: {request}")
    return f"Request logged: {request}"


@activity.defn
async def process_approval(request: str, comment: str) -> str:
    msg = f"[ApprovalWorkflow] APPROVED: {request}"
    if comment:
        msg += f" (comment: {comment})"
    print(msg)
    return msg


@activity.defn
async def process_rejection(request: str, comment: str) -> str:
    msg = f"[ApprovalWorkflow] REJECTED: {request}"
    if comment:
        msg += f" (reason: {comment})"
    print(msg)
    return msg


@register_task
class LogRequestTask(SystemTask):
    task_type = "log_request"
    label = "Log Request"
    _activity_fn = log_request

    class Model(BaseModel):
        request: str


@register_task
class ProcessApprovalTask(SystemTask):
    task_type = "process_approval"
    label = "Process Approval"
    _activity_fn = process_approval

    class Model(BaseModel):
        request: str
        comment: str = ""


@register_task
class ProcessRejectionTask(SystemTask):
    task_type = "process_rejection"
    label = "Process Rejection"
    _activity_fn = process_rejection

    class Model(BaseModel):
        request: str
        comment: str = ""
