"""Add workflows table and link tasks to workflows.

Revision ID: 004
Revises: 003
Create Date: 2026-04-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", sa.String(255), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("workflow_type", sa.String(150), nullable=False),
        sa.Column("workflow_key", sa.String(150), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="starting",
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_by", sa.String(150), nullable=True),
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
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_data", postgresql.JSONB(), nullable=True),
        sa.Column("output_data", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("task_queue", sa.String(150), nullable=True),
    )

    # Indexes
    op.create_index("ix_workflows_workflow_id", "workflows", ["workflow_id"], unique=True)
    op.create_index("ix_workflows_status", "workflows", ["status"])
    op.create_index("ix_workflows_workflow_type", "workflows", ["workflow_type"])
    op.create_index("ix_workflows_workflow_key", "workflows", ["workflow_key"])
    op.create_index("ix_workflows_parent_id", "workflows", ["parent_id"])
    op.create_index("ix_workflows_created_at", "workflows", ["created_at"])
    op.create_index(
        "ix_workflows_status_type", "workflows", ["status", "workflow_type"]
    )

    # Link tasks to workflows
    op.add_column(
        "tasks",
        sa.Column(
            "workflow_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_tasks_workflow_record_id", "tasks", ["workflow_record_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_workflow_record_id", table_name="tasks")
    op.drop_column("tasks", "workflow_record_id")
    op.drop_table("workflows")
