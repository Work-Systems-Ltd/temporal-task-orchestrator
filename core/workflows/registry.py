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
    input_task: Type[HumanTask] | None = None
    input_label: str = ""
    input_placeholder: str = ""
    task_types: list[Type[HumanTask]] = field(default_factory=list)
    required_users: list[str] = field(default_factory=list)
    required_groups: list[str] = field(default_factory=list)

    def can_access(self, user_slug: str, user_group_slugs: list[str], is_admin: bool = False) -> bool:
        """Whether the given user is allowed to see and start this workflow."""
        if is_admin:
            return True
        if not self.required_users and not self.required_groups:
            return True
        if self.required_users and user_slug in self.required_users:
            return True
        if self.required_groups and any(g in self.required_groups for g in user_group_slugs):
            return True
        return False


_WORKFLOW_REGISTRY: dict[str, WorkflowDef] = {}


def register_workflow(
    *,
    key: str,
    label: str,
    description: str,
    task_types: list[Type[HumanTask]] | None = None,
    input_label: str = "",
    input_placeholder: str = "",
    required_users: list[str] | None = None,
    required_groups: list[str] | None = None,
):
    """Class decorator factory that registers a WorkSysFlow subclass.

    Usage::

        @register_workflow(
            key="approval",
            label="Approval",
            description="Submit a request...",
            task_types=[ApprovalTask],
        )
        @workflow.defn
        class ApprovalWorkflow(WorkSysFlow):
            input_task = ApprovalInputTask
            ...
    """
    def decorator(cls: Type[WorkSysFlow]) -> Type[WorkSysFlow]:
        if not hasattr(cls, "input_task"):
            raise ValueError(
                f"{cls.__name__} must declare an 'input_task' ClassVar "
                f"(set to a HumanTask class or None)"
            )

        cls._workflow_key = key

        _WORKFLOW_REGISTRY[key] = WorkflowDef(
            key=key,
            label=label,
            description=description,
            workflow_cls=cls,
            input_task=cls.input_task,
            input_label=input_label,
            input_placeholder=input_placeholder,
            task_types=task_types or [],
            required_users=required_users or [],
            required_groups=required_groups or [],
        )
        return cls

    return decorator


def get_workflow(key: str) -> WorkflowDef:
    if key not in _WORKFLOW_REGISTRY:
        raise KeyError(f"Unknown workflow: {key!r}")
    return _WORKFLOW_REGISTRY[key]


def get_all_workflows() -> list[WorkflowDef]:
    return list(_WORKFLOW_REGISTRY.values())


async def validate_assignments() -> None:
    """Warn if any required_users or required_groups don't exist in the database."""
    import logging

    from sqlalchemy import select

    from ui.auth.database import get_session_factory
    from ui.auth.models import Group, User, _slugify

    logger = logging.getLogger(__name__)

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
            existing_slugs = {_slugify(row[0]) for row in result}
            missing = all_users - existing_slugs
            if missing:
                for wf in _WORKFLOW_REGISTRY.values():
                    bad = set(wf.required_users) & missing
                    if bad:
                        logger.warning(
                            "Workflow %r references unknown user slug(s): %s "
                            "— assignments to these users will be ignored at runtime",
                            wf.key, bad,
                        )

        if all_groups:
            result = await db.execute(select(Group.name))
            existing_slugs = {_slugify(row[0]) for row in result}
            missing = all_groups - existing_slugs
            if missing:
                for wf in _WORKFLOW_REGISTRY.values():
                    bad = set(wf.required_groups) & missing
                    if bad:
                        logger.warning(
                            "Workflow %r references unknown group slug(s): %s "
                            "— assignments to these groups will be ignored at runtime",
                            wf.key, bad,
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
        for task_cls in wf.task_types:
            if task_cls.task_type not in known_task_types:
                raise ValueError(
                    f"Workflow {wf.key!r} references task "
                    f"{task_cls.__name__!r} (task_type={task_cls.task_type!r}) "
                    f"which is not registered"
                )
