from pydantic import BaseModel, Field
from wtforms import SelectField, TextAreaField, validators

from human_tasks.base import HumanTask, TaskForm
from human_tasks.registry import register_task


@register_task
class OnboardingTask(HumanTask):
    task_type = "onboarding"

    class Form(TaskForm):
        team = SelectField(
            "Team",
            choices=[
                ("engineering", "Engineering"),
                ("design", "Design"),
                ("product", "Product"),
                ("marketing", "Marketing"),
                ("operations", "Operations"),
            ],
            validators=[validators.DataRequired()],
        )
        equipment = SelectField(
            "Equipment",
            choices=[
                ("macbook_pro_16", 'MacBook Pro 16"'),
                ("macbook_pro_14", 'MacBook Pro 14"'),
                ("macbook_air", "MacBook Air"),
                ("thinkpad_x1", "ThinkPad X1 Carbon"),
                ("custom", "Custom (specify in notes)"),
            ],
            validators=[validators.DataRequired()],
        )
        notes = TextAreaField(
            "Notes",
            validators=[validators.Optional(), validators.Length(max=1000)],
        )

    class Model(BaseModel):
        team: str = Field(pattern=r"^(engineering|design|product|marketing|operations)$")
        equipment: str = Field(
            pattern=r"^(macbook_pro_16|macbook_pro_14|macbook_air|thinkpad_x1|custom)$"
        )
        notes: str = ""
