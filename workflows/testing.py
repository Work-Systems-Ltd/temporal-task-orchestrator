from temporalio import workflow
from temporalio.common import RetryPolicy

from core.workflows import WorkSysFlow, register_workflow
from tasks.human.testing_input import TestingInputTask
from tasks.system.testing import validate_input, process_data, finalize


STEPS = {
    "step_1": validate_input,
    "step_2": process_data,
    "step_3": finalize,
}

STEP_ORDER = ["step_1", "step_2", "step_3"]


@register_workflow(
    key="testing",
    label="Testing",
    description="Configurable test workflow — can succeed or fail at a chosen step",
)
@workflow.defn
class TestingWorkflow(WorkSysFlow):
    input_task = TestingInputTask

    @workflow.run
    async def run(self, input: TestingInputTask.Model) -> str:
        await self._persist_workflow_started(input)
        try:
            results = []
            for step_key in STEP_ORDER:
                step_activity = STEPS[step_key]
                should_fail = input.should_fail and input.fail_at_step == step_key
                result = await self.create_system_task(
                    step_activity,
                    input.message, should_fail,
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
                results.append(result)

            result = " | ".join(results)
            await self._persist_workflow_completed(result)
            return result
        except Exception as exc:
            await self._persist_workflow_failed(str(exc))
            raise
