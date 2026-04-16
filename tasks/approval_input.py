from pydantic import BaseModel, Field
from wtforms import SelectField, TextAreaField, validators

from core.tasks import HumanTask, TaskForm, register_task


@register_task
class ApprovalInputTask(HumanTask):
    task_type = "approval_input"

    class Form(TaskForm):
        description = TextAreaField(
            "Request description",
            validators=[validators.DataRequired(), validators.Length(max=1000)],
        )
        urgency = SelectField(
            "Urgency",
            choices=[("normal", "Normal"), ("high", "High"), ("critical", "Critical")],
            validators=[validators.DataRequired()],
        )

    class Model(BaseModel):
        description: str = Field(min_length=1, max_length=1000)
        urgency: str = Field(pattern=r"^(normal|high|critical)$")
