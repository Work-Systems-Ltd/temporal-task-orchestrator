from datetime import timedelta

from temporalio import activity, workflow

from core.workflows import WorkSysFlow
from tasks.onboarding_input import OnboardingInputTask


@activity.defn
async def create_onboarding_ticket(employee: str) -> str:
    print(f"[OnboardingWorkflow] Ticket created for: {employee}")
    return f"Onboarding ticket created for {employee}"


@activity.defn
async def provision_equipment(employee: str, equipment: str) -> str:
    print(f"[OnboardingWorkflow] Provisioning {equipment} for {employee}")
    return f"Equipment provisioned: {equipment}"


@activity.defn
async def setup_accounts(employee: str, team: str) -> str:
    print(f"[OnboardingWorkflow] Setting up accounts for {employee} in {team}")
    return f"Accounts created for {employee} in {team}"


@workflow.defn
class OnboardingWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, input: OnboardingInputTask.Model) -> str:
        human_data = await self.execute_and_wait(
            create_onboarding_ticket,
            input.employee_name,
            task_type="onboarding",
            title=f"Onboard: {input.employee_name}",
            description=f"Complete the onboarding checklist for {input.employee_name}.",
        )

        team = human_data["team"]
        equipment = human_data["equipment"]
        notes = human_data.get("notes", "")

        await workflow.execute_activity(
            provision_equipment,
            args=[input.employee_name, equipment],
            start_to_close_timeout=timedelta(seconds=10),
        )

        await workflow.execute_activity(
            setup_accounts,
            args=[input.employee_name, team],
            start_to_close_timeout=timedelta(seconds=10),
        )

        result = f"Onboarding complete for {input.employee_name}: team={team}, equipment={equipment}"
        if notes:
            result += f", notes={notes}"
        return result
