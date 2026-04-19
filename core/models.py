from __future__ import annotations

from pydantic import BaseModel


class TaskMeta(BaseModel):
    task_type: str
    title: str
    description: str
    assigned_user: str = ""   # user slug
    assigned_group: str = ""  # group slug
