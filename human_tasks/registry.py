from __future__ import annotations

from typing import Type

from pydantic import BaseModel
from wtforms import Form

_TASK_REGISTRY: dict[str, tuple[Type[Form], Type[BaseModel]]] = {}


def human_task(task_type: str):
    def decorator(form_cls: Type[Form]):
        model_cls = getattr(form_cls, "Model", None)
        if model_cls is None or not (
            isinstance(model_cls, type) and issubclass(model_cls, BaseModel)
        ):
            raise ValueError(
                f"{form_cls.__name__} must define an inner 'class Model(BaseModel)'"
            )
        _TASK_REGISTRY[task_type] = (form_cls, model_cls)
        return form_cls

    return decorator


def get_task(task_type: str) -> tuple[Type[Form], Type[BaseModel]]:
    if task_type not in _TASK_REGISTRY:
        raise KeyError(f"Unknown task type: {task_type!r}")
    return _TASK_REGISTRY[task_type]


def get_all_task_types() -> list[str]:
    return list(_TASK_REGISTRY.keys())
