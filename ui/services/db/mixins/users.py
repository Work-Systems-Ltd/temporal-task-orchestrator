"""Mixin for user CRUD operations."""

from __future__ import annotations

import bcrypt
from sqlalchemy import func, select

from ui.auth.models import Group, User, _slugify


class UsersMixin:
    """User queries and mutations."""

    async def get_user_by_username(self, username: str, active_only: bool = False) -> User | None:
        async with self._session() as db:
            stmt = select(User).where(User.username == username)
            if active_only:
                stmt = stmt.where(User.is_active.is_(True))
            return (await db.execute(stmt)).scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> User | None:
        async with self._session() as db:
            return (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    async def list_users(self, search: str | None = None) -> list[User]:
        async with self._session() as db:
            stmt = select(User).order_by(User.username)
            if search:
                stmt = stmt.where(User.username.ilike(f"%{search}%"))
            return list((await db.execute(stmt)).scalars().all())

    async def count_users(self) -> int:
        async with self._session() as db:
            return (await db.execute(select(func.count(User.id)))).scalar() or 0

    async def create_user(
        self, username: str, password: str, display_name: str = "", group_ids: list[str] | None = None,
    ) -> User | None:
        """Create a user. Returns None if username already exists."""
        async with self._session() as db:
            existing = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
            if existing:
                return None

            groups: list[Group] = []
            for gid in (group_ids or []):
                g = (await db.execute(select(Group).where(Group.id == gid))).scalar_one_or_none()
                if g:
                    groups.append(g)

            user = User(
                username=username,
                display_name=display_name or username,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                groups=groups,
            )
            db.add(user)
            await db.commit()
            return user

    async def reset_password(self, user_id: str, password: str) -> bool:
        async with self._session() as db:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                return False
            user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            await db.commit()
            return True

    async def delete_user(self, user_id: str) -> bool:
        async with self._session() as db:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                return False
            await db.delete(user)
            await db.commit()
            return True

    async def update_user_groups(self, user_id: str, group_ids: list[str]) -> bool:
        async with self._session() as db:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                return False
            groups: list[Group] = []
            for gid in group_ids:
                g = (await db.execute(select(Group).where(Group.id == gid))).scalar_one_or_none()
                if g:
                    groups.append(g)
            user.groups = groups
            await db.commit()
            return True

    async def get_assignable_users(self, group_slug: str | None = None) -> list[dict]:
        """Return user list for assignment. Optionally filter by group membership."""
        async with self._session() as db:
            if group_slug:
                grp = (await db.execute(select(Group).where(Group.name == group_slug))).scalar_one_or_none()
                if not grp:
                    grp = (await db.execute(
                        select(Group).where(func.lower(Group.name) == group_slug.lower())
                    )).scalar_one_or_none()
                if grp:
                    return [{"slug": _slugify(u.username), "label": u.username} for u in grp.users if u.is_active]
                return []
            result = await db.execute(select(User.username).where(User.is_active.is_(True)))
            return [{"slug": _slugify(r[0]), "label": r[0]} for r in result]

    async def get_assignable_groups(self) -> list[dict]:
        async with self._session() as db:
            result = await db.execute(select(Group.name))
            return [{"slug": _slugify(r[0]), "label": r[0]} for r in result]

    async def seed_user(self, username: str, password: str, group_names: list[str]) -> None:
        """Create a user and groups if they don't exist. Update group membership if user exists."""
        import logging
        logger = logging.getLogger(__name__)

        async with self._session() as db:
            for name in group_names:
                if not (await db.execute(select(Group).where(Group.name == name))).scalar_one_or_none():
                    db.add(Group(name=name))
                    logger.info("Created group '%s'", name)
            await db.flush()

            existing = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
            if existing:
                existing_names = {g.name for g in existing.groups}
                for name in group_names:
                    if name not in existing_names:
                        existing.groups.append((await db.execute(select(Group).where(Group.name == name))).scalar_one())
                        logger.info("Added user '%s' to group '%s'", username, name)
            else:
                groups: list[Group] = []
                for name in group_names:
                    groups.append((await db.execute(select(Group).where(Group.name == name))).scalar_one())
                db.add(User(
                    username=username,
                    display_name=username,
                    password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                    groups=groups,
                ))
                logger.info("Created user '%s'", username)
            await db.commit()
