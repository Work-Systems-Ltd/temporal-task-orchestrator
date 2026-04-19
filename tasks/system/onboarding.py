from pydantic import BaseModel
from temporalio import activity

from core.tasks import SystemTask, register_task


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


@register_task
class CreateOnboardingTicketTask(SystemTask):
    task_type = "create_onboarding_ticket"
    label = "Create Ticket"
    _activity_fn = create_onboarding_ticket

    class Model(BaseModel):
        employee: str


@register_task
class ProvisionEquipmentTask(SystemTask):
    task_type = "provision_equipment"
    label = "Provision Equipment"
    _activity_fn = provision_equipment

    class Model(BaseModel):
        employee: str
        equipment: str


@register_task
class SetupAccountsTask(SystemTask):
    task_type = "setup_accounts"
    label = "Setup Accounts"
    _activity_fn = setup_accounts

    class Model(BaseModel):
        employee: str
        team: str
