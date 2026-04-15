from pydantic import BaseModel, Field
from wtforms import SelectField, TextAreaField, validators

from human_tasks.base import HumanTask, TaskForm
from human_tasks.registry import register_task


@register_task
class ApprovalTask(HumanTask):
    task_type = "approval"

    class Form(TaskForm):
        decision = SelectField(
            "Decision",
            choices=[("approve", "Approve"), ("reject", "Reject")],
            validators=[validators.DataRequired()],
        )
        comment = TextAreaField(
            "Comment",
            validators=[validators.Optional(), validators.Length(max=500)],
        )

    class Model(BaseModel):
        decision: str = Field(pattern=r"^(approve|reject)$")
        comment: str = ""
