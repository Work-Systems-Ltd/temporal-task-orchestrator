from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Type

from workflows.base import HumanTaskWorkflow

if TYPE_CHECKING:
    from human_tasks.base import HumanTask


@dataclass
class WorkflowDef:
    key: str
    label: str
    description: str
    workflow_cls: Type[HumanTaskWorkflow]
    input_label: str
    input_placeholder: str
    input_task: Type[HumanTask] | None = None
    task_types: list[str] = field(default_factory=list)


_WORKFLOW_REGISTRY: dict[str, WorkflowDef] = {}


def register_workflow(
    key: str,
    label: str,
    description: str,
    workflow_cls: Type[HumanTaskWorkflow],
    input_label: str,
    input_placeholder: str,
    input_task: Type[HumanTask] | None = None,
    task_types: list[str] | None = None,
) -> None:
    _WORKFLOW_REGISTRY[key] = WorkflowDef(
        key=key,
        label=label,
        description=description,
        workflow_cls=workflow_cls,
        input_label=input_label,
        input_placeholder=input_placeholder,
        input_task=input_task,
        task_types=task_types or [],
    )


def get_workflow(key: str) -> WorkflowDef:
    if key not in _WORKFLOW_REGISTRY:
        raise KeyError(f"Unknown workflow: {key!r}")
    return _WORKFLOW_REGISTRY[key]


def get_all_workflows() -> list[WorkflowDef]:
    return list(_WORKFLOW_REGISTRY.values())


def validate_registrations() -> None:
    """Validate cross-registry references at startup."""
    from human_tasks.registry import get_all_task_types

    known_task_types = set(get_all_task_types())
    for wf in _WORKFLOW_REGISTRY.values():
        if wf.input_task and wf.input_task.task_type not in known_task_types:
            raise ValueError(
                f"Workflow {wf.key!r} references input_task "
                f"{wf.input_task.__name__!r} (task_type={wf.input_task.task_type!r}) "
                f"which is not registered"
            )
        for tt in wf.task_types:
            if tt not in known_task_types:
                raise ValueError(
                    f"Workflow {wf.key!r} references task_type "
                    f"{tt!r} which is not registered"
                )
