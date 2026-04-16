from pydantic import BaseModel, Field
from wtforms import SelectField, validators

from core.tasks import HumanTask, TaskForm, register_task


@register_task
class HiringInputTask(HumanTask):
    task_type = "hiring_input"

    class Form(TaskForm):
        urgency = SelectField(
            "Urgency",
            choices=[("normal", "Normal"), ("high", "High"), ("critical", "Critical")],
            validators=[validators.DataRequired()],
        )

    class Model(BaseModel):
        urgency: str = Field(pattern=r"^(normal|high|critical)$")
