from __future__ import annotations

import re
import unicodedata
import uuid
from functools import cached_property
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import UUID
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

    @property
    def slug(self) -> str:
        return _slugify(self.name)

    def __repr__(self) -> str:
        return f"<Group {self.name}>"


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
