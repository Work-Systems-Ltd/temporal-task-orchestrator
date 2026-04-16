from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Type


@dataclass
class WorkflowDef:
    key: str
    label: str
    description: str
    workflow_cls: Type[Any]
    input_label: str
    input_placeholder: str
    input_task_type: str | None = None
    task_types: list[str] | None = None


_WORKFLOW_REGISTRY: dict[str, WorkflowDef] = {}


def register_workflow(
    key: str,
    label: str,
    description: str,
    workflow_cls: Type[Any],
    input_label: str,
    input_placeholder: str,
    input_task_type: str | None = None,
    task_types: list[str] | None = None,
) -> None:
    _WORKFLOW_REGISTRY[key] = WorkflowDef(
        key=key,
        label=label,
        description=description,
        workflow_cls=workflow_cls,
        input_label=input_label,
        input_placeholder=input_placeholder,
        input_task_type=input_task_type,
        task_types=task_types,
    )


def get_workflow(key: str) -> WorkflowDef:
    if key not in _WORKFLOW_REGISTRY:
        raise KeyError(f"Unknown workflow: {key!r}")
    return _WORKFLOW_REGISTRY[key]


def get_all_workflows() -> list[WorkflowDef]:
    return list(_WORKFLOW_REGISTRY.values())
