from pydantic import BaseModel
from temporalio import activity

from core.tasks import SystemTask, register_task


@activity.defn
async def validate_input(message: str, should_fail: bool) -> str:
    if should_fail:
        raise RuntimeError(f"Validation failed for: {message}")
    print(f"[TestingWorkflow] Input validated: {message}")
    return f"Validated: {message}"


@activity.defn
async def process_data(message: str, should_fail: bool) -> str:
    if should_fail:
        raise RuntimeError(f"Processing failed for: {message}")
    print(f"[TestingWorkflow] Data processed: {message}")
    return f"Processed: {message}"


@activity.defn
async def finalize(message: str, should_fail: bool) -> str:
    if should_fail:
        raise RuntimeError(f"Finalization failed for: {message}")
    print(f"[TestingWorkflow] Finalized: {message}")
    return f"Finalized: {message}"


@register_task
class ValidateInputTask(SystemTask):
    task_type = "validate_input"
    label = "Validate Input"
    _activity_fn = validate_input

    class Model(BaseModel):
        message: str
        should_fail: bool = False


@register_task
class ProcessDataTask(SystemTask):
    task_type = "process_data"
    label = "Process Data"
    _activity_fn = process_data

    class Model(BaseModel):
        message: str
        should_fail: bool = False


@register_task
class FinalizeTask(SystemTask):
    task_type = "finalize"
    label = "Finalize"
    _activity_fn = finalize

    class Model(BaseModel):
        message: str
        should_fail: bool = False
