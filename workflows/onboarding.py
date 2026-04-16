import json
from datetime import timedelta

from temporalio import activity, workflow


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
class OnboardingWorkflow:
    def __init__(self):
        self._human_task_complete = False
        self._human_task_data: dict | None = None
        self._pending_task: dict | None = None

    @workflow.signal
    async def complete_human_task(self, data: str) -> None:
        self._human_task_data = json.loads(data)
        self._human_task_complete = True

    @workflow.query
    def get_pending_task(self) -> str:
        if self._pending_task:
            return json.dumps(self._pending_task)
        return ""

    @workflow.run
    async def run(self, employee: str) -> str:
        # Parse structured input (from input task) or use raw string
        try:
            input_data = json.loads(employee)
            employee_name = input_data.get("employee_name", employee)
            employee_email = input_data.get("employee_email", "")
        except (json.JSONDecodeError, TypeError):
            employee_name = employee
            employee_email = ""

        await workflow.execute_activity(
            create_onboarding_ticket,
            employee_name,
            start_to_close_timeout=timedelta(seconds=10),
        )

        self._pending_task = {
            "task_type": "onboarding",
            "title": f"Onboard: {employee_name}",
            "description": f"Complete the onboarding checklist for {employee_name}.",
        }

        await workflow.wait_condition(lambda: self._human_task_complete)

        self._pending_task = None
        team = self._human_task_data["team"]
        equipment = self._human_task_data["equipment"]
        notes = self._human_task_data.get("notes", "")

        await workflow.execute_activity(
            provision_equipment,
            args=[employee_name, equipment],
            start_to_close_timeout=timedelta(seconds=10),
        )

        await workflow.execute_activity(
            setup_accounts,
            args=[employee_name, team],
            start_to_close_timeout=timedelta(seconds=10),
        )

        result = f"Onboarding complete for {employee_name}: team={team}, equipment={equipment}"
        if notes:
            result += f", notes={notes}"
        return result
