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

class Task(ABC):

    task_type: ClassVar[str]
    color: ClassVar[str] = "zinc"
    label: ClassVar[str] = ""

    @abstractmethod
    class Model(BaseModel):
        ...

class SystemTask(Task):
    """Task type for automated system actions. No human interaction required.

    Subclasses must define:
        task_type: A unique string identifier for this task type.
        Model: A Pydantic BaseModel subclass for the activity input.
        run: An async method containing the task logic.

    Example::

        class LogRequestTask(SystemTask):
            task_type = "log_request"
            label = "Log Request"

            class Model(BaseModel):
                request: str

            async def run(self, request: str) -> str:
                print(f"Request logged: {request}")
                return f"Logged: {request}"
    """

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Override this method with the task logic."""
        raise NotImplementedError

class HumanTask(Task):
    """Abstract base class for human tasks.

    Subclasses must define:
        task_type: A unique string identifier for this task type.
        Form: A TaskForm subclass defining the HTML form fields.
        Model: A Pydantic BaseModel subclass for server-side validation.

    Subclasses may override:
        pre_submit: Custom validation logic run after Pydantic validation
                    but before the task is signalled as complete.
    """
    @abstractmethod
    class Form(TaskForm):
        ...

    async def pre_submit(self, model: BaseModel) -> dict[str, list[str]] | None:
        """Optional validation hook called after Pydantic model construction.

        Args:
            model: The validated Pydantic model instance.

        Returns:
            None if validation passes, or a dict mapping field names to
            lists of error messages if validation fails.
        """
        return None
