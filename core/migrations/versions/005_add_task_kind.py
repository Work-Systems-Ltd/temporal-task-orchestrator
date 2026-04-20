"""Add task_kind column to tasks table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "task_kind",
            sa.String(20),
            nullable=False,
            server_default="human",
        ),
    )
    op.create_index("ix_tasks_task_kind", "tasks", ["task_kind"])


def downgrade() -> None:
    op.drop_index("ix_tasks_task_kind", table_name="tasks")
    op.drop_column("tasks", "task_kind")
