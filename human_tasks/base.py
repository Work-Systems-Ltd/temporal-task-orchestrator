from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Type

from pydantic import BaseModel
from wtforms import Form


class TaskForm(Form):
    """Base form class for human task forms.

    All human task forms should extend this class instead of
    wtforms.Form directly.
    """

    def to_model(self, model_cls: Type[BaseModel]) -> BaseModel:
        """Convert validated form data to a Pydantic model instance.

        Override this method for custom form-to-model mapping.
        The default implementation maps each form field by name.
        """
        return model_cls(**{field.name: field.data for field in self})


class HumanTask(ABC):
    """Abstract base class for human tasks.

    Subclasses must define:
        task_type: A unique string identifier for this task type.
        Form: A TaskForm subclass defining the HTML form fields.
        Model: A Pydantic BaseModel subclass for server-side validation.

    Subclasses may override:
        pre_submit: Custom validation logic run after Pydantic validation
                    but before the task is signalled as complete.
    """

    task_type: ClassVar[str]

    @abstractmethod
    class Form(TaskForm):
        ...

    @abstractmethod
    class Model(BaseModel):
        ...

    def pre_submit(self, model: BaseModel) -> dict[str, list[str]] | None:
        """Optional validation hook called after Pydantic model construction.

        Args:
            model: The validated Pydantic model instance.

        Returns:
            None if validation passes, or a dict mapping field names to
            lists of error messages if validation fails.
        """
        return None
