from temporalio import workflow

from core.workflows import WorkSysFlow
from tasks.human.onboarding import OnboardingTask
from tasks.human.onboarding_input import OnboardingInputTask
from tasks.system.onboarding import CreateOnboardingTicketTask, ProvisionEquipmentTask, SetupAccountsTask


@workflow.defn
class OnboardingWorkflow(WorkSysFlow):

    @workflow.run
    async def run(self, input: OnboardingInputTask.Model) -> str:
        await self.create_system_task(CreateOnboardingTicketTask, input.employee_name)

        human_data = await self.wait_for_task(
            OnboardingTask,
            title=f"Onboard: {input.employee_name}",
            description=f"Complete the onboarding checklist for {input.employee_name}.",
            assigned_user="admin",
        )

        team = human_data["team"]
        equipment = human_data["equipment"]
        notes = human_data.get("notes", "")

        await self.create_system_task(ProvisionEquipmentTask, input.employee_name, equipment)
        await self.create_system_task(SetupAccountsTask, input.employee_name, team)

        result = f"Onboarding complete for {input.employee_name}: team={team}, equipment={equipment}"
        if notes:
            result += f", notes={notes}"
        return result
