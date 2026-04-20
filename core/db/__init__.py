"""Core database package — models, engine, and service."""

from core.db.engine import dispose_engine, get_session_factory, init_engine
from core.db.models import (
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
from core.db.service import DbService

__all__ = [
    "Base",
    "DbService",
    "Group",
    "Session",
    "TaskActivityLog",
    "TaskComment",
    "TaskRecord",
    "User",
    "WorkflowRecord",
    "_slugify",
    "dispose_engine",
    "get_session_factory",
    "init_engine",
    "user_groups",
]
