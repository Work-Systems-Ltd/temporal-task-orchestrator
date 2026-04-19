"""Mixin for group CRUD operations."""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from ui.auth.models import Group

logger = logging.getLogger(__name__)


class GroupsMixin:
    """Group queries and mutations."""

    async def list_groups(self, search: str | None = None) -> list[Group]:
        async with self._session() as db:
            stmt = select(Group).order_by(Group.name)
            if search:
                stmt = stmt.where(Group.name.ilike(f"%{search}%"))
            return list((await db.execute(stmt)).scalars().all())

    async def count_groups(self) -> int:
        async with self._session() as db:
            return (await db.execute(select(func.count(Group.id)))).scalar() or 0

    async def get_group_by_name(self, name: str) -> Group | None:
        async with self._session() as db:
            return (await db.execute(select(Group).where(Group.name == name))).scalar_one_or_none()

    async def create_group(self, name: str) -> Group | None:
        """Create a group. Returns None if name already exists."""
        async with self._session() as db:
            if (await db.execute(select(Group).where(Group.name == name))).scalar_one_or_none():
                return None
            group = Group(name=name)
            db.add(group)
            await db.commit()
            return group

    async def delete_group(self, group_id: str) -> bool:
        async with self._session() as db:
            group = (await db.execute(select(Group).where(Group.id == group_id))).scalar_one_or_none()
            if not group:
                return False
            await db.delete(group)
            await db.commit()
            return True

    async def ensure_groups(self, names: list[str]) -> None:
        """Create groups if they don't already exist."""
        async with self._session() as db:
            for name in names:
                if not (await db.execute(select(Group).where(Group.name == name))).scalar_one_or_none():
                    db.add(Group(name=name))
                    logger.info("Created default group '%s'", name)
            await db.commit()
