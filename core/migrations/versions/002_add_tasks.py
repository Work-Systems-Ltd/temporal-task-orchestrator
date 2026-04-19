"""Add tasks table for task persistence and lifecycle management.

Revision ID: 002
Revises: 001
Create Date: 2026-04-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", sa.String(255), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("task_type", sa.String(150), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("assigned_user", sa.String(150), nullable=True),
        sa.Column("assigned_group", sa.String(150), nullable=True),
        sa.Column("created_by", sa.String(150), nullable=True),
        sa.Column("completed_by", sa.String(150), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form_data", postgresql.JSONB(), nullable=True),
        sa.Column("task_metadata", postgresql.JSONB(), nullable=True),
    )

    # Single-column indexes
    op.create_index("ix_tasks_workflow_id", "tasks", ["workflow_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_task_type", "tasks", ["task_type"])
    op.create_index("ix_tasks_assigned_user", "tasks", ["assigned_user"])
    op.create_index("ix_tasks_assigned_group", "tasks", ["assigned_group"])
    op.create_index("ix_tasks_created_at", "tasks", ["created_at"])

    # Composite indexes for common query patterns
    op.create_index(
        "ix_tasks_status_assigned_user", "tasks", ["status", "assigned_user"]
    )
    op.create_index(
        "ix_tasks_status_assigned_group", "tasks", ["status", "assigned_group"]
    )


def downgrade() -> None:
    op.drop_table("tasks")
