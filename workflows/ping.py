from temporalio import workflow

from core.workflows import WorkSysFlow, register_workflow
from tasks.system.ping import ping


@register_workflow(
    key="ping",
    label="Ping",
    description="Ping an IP address to check connectivity",
    input_label="IP Address",
    input_placeholder="e.g. 8.8.8.8",
)
@workflow.defn
class PingWorkflow(WorkSysFlow):
    input_task = None

    @workflow.run
    async def run(self, ip_address: str) -> str:
        await self._persist_workflow_started(ip_address)
        try:
            result = await self.create_system_task(ping, ip_address)
            await self._persist_workflow_completed(result)
            return result
        except Exception as exc:
            await self._persist_workflow_failed(str(exc))
            raise
