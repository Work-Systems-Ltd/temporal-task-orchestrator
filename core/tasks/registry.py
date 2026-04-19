from __future__ import annotations

from typing import Type

from temporalio import activity

from core.tasks.base import HumanTask, SystemTask, Task

_TASK_REGISTRY: dict[str, Task] = {}


def register_task(cls: Type[Task]) -> Type[Task]:
    """Class decorator that registers a Task subclass (HumanTask or SystemTask).

    For SystemTask subclasses, automatically wraps the ``run`` method
    as a Temporal ``@activity.defn`` and stores it on ``cls._activity``.
    """
    if not hasattr(cls, "task_type"):
        raise ValueError(f"{cls.__name__} must define a 'task_type' class attribute")
    if not hasattr(cls, "Model"):
        raise ValueError(f"{cls.__name__} must define an inner 'Model' class")

    if issubclass(cls, HumanTask) and not hasattr(cls, "Form"):
        raise ValueError(f"{cls.__name__} must define an inner 'Form' class")

    if issubclass(cls, SystemTask):
        # Auto-generate a Temporal activity from the run method
        instance = cls()
        _run = instance.run

        async def _make_activity(*args):
            return await _run(*args)

        _make_activity.__name__ = cls.task_type
        _make_activity.__qualname__ = f"{cls.__name__}.run"
        cls._activity = activity.defn(name=cls.task_type)(_make_activity)
    else:
        instance = cls()

    _TASK_REGISTRY[cls.task_type] = instance
    return cls


def get_task(task_type: str) -> Task:
    """Retrieve a registered Task instance by type."""
    if task_type not in _TASK_REGISTRY:
        raise KeyError(f"Unknown task type: {task_type!r}")
    return _TASK_REGISTRY[task_type]


def get_human_task(task_type: str) -> HumanTask:
    """Retrieve a registered HumanTask instance by type."""
    task = get_task(task_type)
    if not isinstance(task, HumanTask):
        raise KeyError(f"Task {task_type!r} is not a HumanTask")
    return task


def get_all_task_types() -> list[str]:
    return list(_TASK_REGISTRY.keys())


def get_all_activities() -> list:
    """Return all activity functions from registered SystemTasks."""
    return [
        task._activity
        for task in _TASK_REGISTRY.values()
        if isinstance(task, SystemTask) and hasattr(task, "_activity")
    ]


def get_task_color(task_type: str) -> str:
    """Return the pill color for a task type, defaulting to 'zinc'."""
    task = _TASK_REGISTRY.get(task_type)
    return task.color if task else "zinc"


def get_task_label(task_type: str) -> str:
    """Return the display label for a task type, defaulting to the task_type string."""
    task = _TASK_REGISTRY.get(task_type)
    return task.label if task and task.label else task_type
