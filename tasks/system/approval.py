from pydantic import BaseModel

from core.tasks import SystemTask, register_task


@register_task
class LogRequestTask(SystemTask):
    task_type = "log_request"
    label = "Log Request"

    class Model(BaseModel):
        request: str

    async def run(self, request: str) -> str:
        print(f"[ApprovalWorkflow] New request logged: {request}")
        return f"Request logged: {request}"


@register_task
class ProcessApprovalTask(SystemTask):
    task_type = "process_approval"
    label = "Process Approval"

    class Model(BaseModel):
        request: str
        comment: str = ""

    async def run(self, request: str, comment: str) -> str:
        msg = f"[ApprovalWorkflow] APPROVED: {request}"
        if comment:
            msg += f" (comment: {comment})"
        print(msg)
        return msg


@register_task
class ProcessRejectionTask(SystemTask):
    task_type = "process_rejection"
    label = "Process Rejection"

    class Model(BaseModel):
        request: str
        comment: str = ""

    async def run(self, request: str, comment: str) -> str:
        msg = f"[ApprovalWorkflow] REJECTED: {request}"
        if comment:
            msg += f" (reason: {comment})"
        print(msg)
        return msg
