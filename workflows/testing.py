from temporalio import workflow
from temporalio.common import RetryPolicy

from core.workflows import WorkSysFlow
from tasks.human.testing_input import TestingInputTask
from tasks.system.testing import ValidateInputTask, ProcessDataTask, FinalizeTask


STEPS = {
    "step_1": ValidateInputTask,
    "step_2": ProcessDataTask,
    "step_3": FinalizeTask,
}

STEP_ORDER = ["step_1", "step_2", "step_3"]


@workflow.defn
class TestingWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, input: TestingInputTask.Model) -> str:
        results = []
        for step_key in STEP_ORDER:
            step_task = STEPS[step_key]
            should_fail = input.should_fail and input.fail_at_step == step_key
            result = await self.create_system_task(
                step_task,
                input.message, should_fail,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            results.append(result)

        return " | ".join(results)
