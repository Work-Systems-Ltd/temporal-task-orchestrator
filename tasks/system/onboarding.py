from pydantic import BaseModel

from core.tasks import SystemTask, register_task


@register_task
class CreateOnboardingTicketTask(SystemTask):
    task_type = "create_onboarding_ticket"
    label = "Create Ticket"

    class Model(BaseModel):
        employee: str

    @staticmethod
    async def run( employee: str) -> str:
        print(f"[OnboardingWorkflow] Ticket created for: {employee}")
        return f"Onboarding ticket created for {employee}"


@register_task
class ProvisionEquipmentTask(SystemTask):
    task_type = "provision_equipment"
    label = "Provision Equipment"

    class Model(BaseModel):
        employee: str
        equipment: str

    @staticmethod
    async def run( employee: str, equipment: str) -> str:
        print(f"[OnboardingWorkflow] Provisioning {equipment} for {employee}")
        return f"Equipment provisioned: {equipment}"


@register_task
class SetupAccountsTask(SystemTask):
    task_type = "setup_accounts"
    label = "Setup Accounts"

    class Model(BaseModel):
        employee: str
        team: str

    @staticmethod
    async def run( employee: str, team: str) -> str:
        print(f"[OnboardingWorkflow] Setting up accounts for {employee} in {team}")
        return f"Accounts created for {employee} in {team}"
