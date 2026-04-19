from datetime import timedelta

from temporalio import activity, workflow

from core.workflows import WorkSysFlow


# Define the activity as a plain module-level function — no class
@activity.defn
async def ping_activity(message: str) -> str:
    print(f"[Ping] {message}")
    return f"pong: {message}"


@workflow.defn
class PingWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, message: str) -> str:
        result = await workflow.execute_activity(
            ping_activity,
            message,
            start_to_close_timeout=timedelta(seconds=10),
        )
        return result
