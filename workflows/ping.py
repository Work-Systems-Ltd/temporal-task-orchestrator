from temporalio import workflow

from core.workflows import WorkSysFlow
from tasks.system.ping import PingTask


@workflow.defn
class PingWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, message: str) -> str:
        result = await self.create_system_task(PingTask, message)
        return result
