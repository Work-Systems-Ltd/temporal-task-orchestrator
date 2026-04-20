"""Backwards-compatibility shim — canonical location is core.db.models."""
from core.db.models import (  # noqa: F401
    Base,
    Group,
    Session,
    TaskActivityLog,
    TaskComment,
    TaskRecord,
    User,
    WorkflowRecord,
    _slugify,
    user_groups,
)
