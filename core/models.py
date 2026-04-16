from __future__ import annotations

from pydantic import BaseModel


class TaskMeta(BaseModel):
    task_type: str
    title: str
    description: str
