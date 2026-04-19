from __future__ import annotations

import re
import unicodedata
import uuid
from functools import cached_property
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-")


user_groups = Table(
    "user_groups",
    Base.metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "group_id",
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    groups: Mapped[list[Group]] = relationship(
        secondary=user_groups, back_populates="users", lazy="selectin"
    )

    @cached_property
    def slug(self) -> str:
        return _slugify(self.username)

    @cached_property
    def is_admin(self) -> bool:
        return any(g.name == "admin" for g in self.groups)

    @cached_property
    def group_slugs(self) -> list[str]:
        return [g.slug for g in self.groups]

    def can_access_task(self, assigned_user: str = "", assigned_group: str = "") -> bool:
        """Whether this user can view and act on a task with the given assignment."""
        if self.is_admin:
            return True
        if not assigned_user and not assigned_group:
            return True  # unassigned → anyone
        if assigned_user and assigned_user == self.slug:
            return True
        if assigned_group and assigned_group in self.group_slugs:
            return True
        return False

    def can_reassign_to(self, user_slug: str = "", group_slug: str = "") -> bool:
        """Whether this user is allowed to reassign a task to the given user/group."""
        if self.is_admin:
            return True
        # Non-admins can only reassign to themselves or their own groups
        if user_slug and user_slug != self.slug:
            return False
        if group_slug and group_slug not in self.group_slugs:
            return False
        return True

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    users: Mapped[list[User]] = relationship(
        secondary=user_groups, back_populates="groups", lazy="selectin"
    )

    @cached_property
    def slug(self) -> str:
        return _slugify(self.name)

    def __repr__(self) -> str:
        return f"<Group {self.name}>"


class TaskRecord(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_status_assigned_user", "status", "assigned_user"),
        Index("ix_tasks_status_assigned_group", "status", "assigned_group"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="open", index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )
    assigned_user: Mapped[str | None] = mapped_column(
        String(150), nullable=True, index=True
    )
    assigned_group: Mapped[str | None] = mapped_column(
        String(150), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    form_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    task_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    comments: Mapped[list[TaskComment]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin",
        order_by="TaskComment.created_at",
    )
    activity_log: Mapped[list[TaskActivityLog]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="noload",
        order_by="TaskActivityLog.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<TaskRecord {self.id} [{self.status}] {self.title[:30]}>"


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author: Mapped[str] = mapped_column(String(150), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[TaskRecord] = relationship(back_populates="comments")

    def __repr__(self) -> str:
        return f"<TaskComment {self.id} by {self.author}>"


class TaskActivityLog(Base):
    __tablename__ = "task_activity_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[TaskRecord] = relationship(back_populates="activity_log")

    def __repr__(self) -> str:
        return f"<TaskActivityLog {self.action} on {self.task_id}>"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    user: Mapped[User] = relationship(lazy="selectin")
