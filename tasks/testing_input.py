from pydantic import BaseModel, Field
from wtforms import BooleanField, SelectField, TextAreaField, validators

from core.tasks import HumanTask, TaskForm, register_task


@register_task
class TestingInputTask(HumanTask):
    task_type = "testing_input"

    class Form(TaskForm):
        message = TextAreaField(
            "Message",
            validators=[validators.DataRequired(), validators.Length(max=500)],
        )
        should_fail = BooleanField("Should fail?", default=False)
        fail_at_step = SelectField(
            "Fail at step",
            choices=[
                ("step_1", "Step 1 — Validate input"),
                ("step_2", "Step 2 — Process data"),
                ("step_3", "Step 3 — Finalize"),
            ],
            validators=[validators.DataRequired()],
        )

    class Model(BaseModel):
        message: str = Field(min_length=1, max_length=500)
        should_fail: bool = False
        fail_at_step: str = Field(default="step_1", pattern=r"^(step_1|step_2|step_3)$")
