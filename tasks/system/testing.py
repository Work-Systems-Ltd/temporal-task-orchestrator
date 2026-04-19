from pydantic import BaseModel

from core.tasks import SystemTask, register_task


@register_task
class ValidateInputTask(SystemTask):
    task_type = "validate_input"
    label = "Validate Input"

    class Model(BaseModel):
        message: str
        should_fail: bool = False

    async def run(self, message: str, should_fail: bool) -> str:
        if should_fail:
            raise RuntimeError(f"Validation failed for: {message}")
        print(f"[TestingWorkflow] Input validated: {message}")
        return f"Validated: {message}"


@register_task
class ProcessDataTask(SystemTask):
    task_type = "process_data"
    label = "Process Data"

    class Model(BaseModel):
        message: str
        should_fail: bool = False

    async def run(self, message: str, should_fail: bool) -> str:
        if should_fail:
            raise RuntimeError(f"Processing failed for: {message}")
        print(f"[TestingWorkflow] Data processed: {message}")
        return f"Processed: {message}"


@register_task
class FinalizeTask(SystemTask):
    task_type = "finalize"
    label = "Finalize"

    class Model(BaseModel):
        message: str
        should_fail: bool = False

    async def run(self, message: str, should_fail: bool) -> str:
        if should_fail:
            raise RuntimeError(f"Finalization failed for: {message}")
        print(f"[TestingWorkflow] Finalized: {message}")
        return f"Finalized: {message}"
