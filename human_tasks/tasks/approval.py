from pydantic import BaseModel, Field
from wtforms import Form, SelectField, TextAreaField, validators

from human_tasks.registry import human_task


@human_task("approval")
class ApprovalForm(Form):
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
