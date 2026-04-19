from datetime import timedelta

from temporalio import activity, workflow

from core.workflows import WorkSysFlow
from tasks.testing_input import TestingInputTask


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


STEPS = {
    "step_1": validate_input,
    "step_2": process_data,
    "step_3": finalize,
}

STEP_ORDER = ["step_1", "step_2", "step_3"]


@workflow.defn
class TestingWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, input: TestingInputTask.Model) -> str:
        results = []
        for step_key in STEP_ORDER:
            step_activity = STEPS[step_key]
            should_fail = input.should_fail and input.fail_at_step == step_key
            result = await workflow.execute_activity(
                step_activity,
                args=[input.message, should_fail],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=workflow.RetryPolicy(maximum_attempts=1),
            )
            results.append(result)

        return " | ".join(results)
