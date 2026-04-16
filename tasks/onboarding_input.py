from pydantic import BaseModel, Field
from wtforms import StringField, validators

from core.tasks import HumanTask, TaskForm, register_task


@register_task
class OnboardingInputTask(HumanTask):
    task_type = "onboarding_input"

    class Form(TaskForm):
        employee_name = StringField(
            "Employee name",
            validators=[validators.DataRequired(), validators.Length(max=200)],
        )
        employee_email = StringField(
            "Employee email",
            validators=[validators.DataRequired(), validators.Email()],
        )

    class Model(BaseModel):
        employee_name: str = Field(min_length=1, max_length=200)
        employee_email: str
