from pydantic import BaseModel, Field
from wtforms import SelectField, StringField, validators

from core.tasks import HumanTask, TaskForm, register_task


@register_task
class HiringInputTask(HumanTask):
    task_type = "hiring_input"
    color = "emerald"
    label = "Hiring Request"

    class Form(TaskForm):
        employee_name = StringField(
            "Employee name",
            validators=[validators.DataRequired(), validators.Length(max=200)],
        )
        urgency = SelectField(
            "Urgency",
            choices=[("normal", "Normal"), ("high", "High"), ("critical", "Critical")],
            validators=[validators.DataRequired()],
        )

    class Model(BaseModel):
        employee_name: str = Field(min_length=1, max_length=200)
        urgency: str = Field(pattern=r"^(normal|high|critical)$")
