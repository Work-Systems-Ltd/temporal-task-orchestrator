from datetime import timedelta

from temporalio import workflow

from core.workflows import WorkSysFlow
from tasks.system.ping import PingTask


@workflow.defn
class PingWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, message: str) -> str:
        # Direct call bypassing create_system_task to debug
        result = await workflow.execute_activity(
            PingTask._activity,
            message,
            start_to_close_timeout=timedelta(seconds=10),
        )
        return result
