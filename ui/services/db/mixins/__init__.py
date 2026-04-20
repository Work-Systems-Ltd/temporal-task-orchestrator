"""Backwards-compatibility shim — canonical location is core.db.mixins."""
from core.db.mixins import GroupsMixin, SessionsMixin, TasksMixin, UsersMixin, WorkflowsMixin  # noqa: F401

__all__ = ["GroupsMixin", "SessionsMixin", "TasksMixin", "UsersMixin", "WorkflowsMixin"]
