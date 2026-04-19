from temporalio import workflow

from core.workflows import WorkSysFlow
from tasks.system.ping import ping


@workflow.defn
class PingWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, message: str) -> str:
        result = await self.create_system_task(ping, message)
        return result
