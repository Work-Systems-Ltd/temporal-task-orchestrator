from __future__ import annotations

from typing import Type

from human_tasks.base import HumanTask

_TASK_REGISTRY: dict[str, HumanTask] = {}


def register_task(cls: Type[HumanTask]) -> Type[HumanTask]:
    """Class decorator that registers a HumanTask subclass."""
    if not hasattr(cls, "task_type"):
        raise ValueError(f"{cls.__name__} must define a 'task_type' class attribute")
    if not hasattr(cls, "Form"):
        raise ValueError(f"{cls.__name__} must define an inner 'Form' class")
    if not hasattr(cls, "Model"):
        raise ValueError(f"{cls.__name__} must define an inner 'Model' class")

    instance = cls()
    _TASK_REGISTRY[cls.task_type] = instance
    return cls


def get_task(task_type: str) -> HumanTask:
    """Retrieve a registered HumanTask instance by type."""
    if task_type not in _TASK_REGISTRY:
        raise KeyError(f"Unknown task type: {task_type!r}")
    return _TASK_REGISTRY[task_type]


def get_all_task_types() -> list[str]:
    return list(_TASK_REGISTRY.keys())
