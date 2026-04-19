from __future__ import annotations

from pydantic import BaseModel


class TaskMeta(BaseModel):
    task_id: str = ""          # UUID from DB, empty until persisted
    task_type: str
    title: str
    description: str
    assigned_user: str = ""    # user slug
    assigned_group: str = ""   # group slug
    priority: str = "medium"   # critical, high, medium, low
    status: str = "open"       # open, in_progress, on_hold, completed, cancelled
