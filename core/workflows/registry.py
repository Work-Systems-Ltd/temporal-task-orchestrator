from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Type

from core.workflows.base import WorkSysFlow

if TYPE_CHECKING:
    from core.tasks.base import HumanTask


@dataclass
class WorkflowDef:
    key: str
    label: str
    description: str
    workflow_cls: Type[WorkSysFlow]
    input_label: str
    input_placeholder: str
    input_task: Type[HumanTask] | None = None
    task_types: list[str] = field(default_factory=list)
    required_users: list[str] = field(default_factory=list)
    required_groups: list[str] = field(default_factory=list)


_WORKFLOW_REGISTRY: dict[str, WorkflowDef] = {}


def register_workflow(
    key: str,
    label: str,
    description: str,
    workflow_cls: Type[WorkSysFlow],
    input_label: str,
    input_placeholder: str,
    input_task: Type[HumanTask] | None = None,
    task_types: list[str] | None = None,
    required_users: list[str] | None = None,
    required_groups: list[str] | None = None,
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
        required_users=required_users or [],
        required_groups=required_groups or [],
    )


def get_workflow(key: str) -> WorkflowDef:
    if key not in _WORKFLOW_REGISTRY:
        raise KeyError(f"Unknown workflow: {key!r}")
    return _WORKFLOW_REGISTRY[key]


def get_all_workflows() -> list[WorkflowDef]:
    return list(_WORKFLOW_REGISTRY.values())


async def validate_assignments() -> None:
    """Validate that all required_users and required_groups exist in the database.

    Must be called after the database engine is initialized.
    """
    from sqlalchemy import select

    from ui.auth.database import get_session_factory
    from ui.auth.models import Group, User

    all_users: set[str] = set()
    all_groups: set[str] = set()

    for wf in _WORKFLOW_REGISTRY.values():
        all_users.update(wf.required_users)
        all_groups.update(wf.required_groups)

    if not all_users and not all_groups:
        return

    factory = get_session_factory()
    async with factory() as db:
        if all_users:
            result = await db.execute(select(User.username))
            existing_users = {row[0] for row in result}
            # Check slugified versions
            from ui.auth.models import _slugify
            existing_slugs = {_slugify(u) for u in existing_users}
            missing = all_users - existing_slugs
            if missing:
                sources = [
                    f"  - {wf.key!r} requires users: {wf.required_users}"
                    for wf in _WORKFLOW_REGISTRY.values()
                    if set(wf.required_users) & missing
                ]
                raise ValueError(
                    f"Unknown user slug(s): {missing}\n" + "\n".join(sources)
                )

        if all_groups:
            result = await db.execute(select(Group.name))
            existing_groups = {row[0] for row in result}
            from ui.auth.models import _slugify
            existing_slugs = {_slugify(g) for g in existing_groups}
            missing = all_groups - existing_slugs
            if missing:
                sources = [
                    f"  - {wf.key!r} requires groups: {wf.required_groups}"
                    for wf in _WORKFLOW_REGISTRY.values()
                    if set(wf.required_groups) & missing
                ]
                raise ValueError(
                    f"Unknown group slug(s): {missing}\n" + "\n".join(sources)
                )


def validate_registrations() -> None:
    """Validate cross-registry references at startup."""
    from core.tasks.registry import get_all_task_types

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
