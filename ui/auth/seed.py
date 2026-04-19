"""Seed script to create initial users and groups.

Usage (standalone CLI):
    python -m ui.auth.seed --username admin --password changeme
    python -m ui.auth.seed --username admin --password changeme --groups admins,operators

The ``seed`` coroutine can also be called directly when the engine is
already initialised (e.g. from the app lifespan).
"""
from __future__ import annotations

import argparse
import asyncio
import logging

import bcrypt
from sqlalchemy import select

from .database import dispose_engine, get_session_factory, init_engine
from .models import Group, User

logger = logging.getLogger(__name__)


async def seed(username: str, password: str, group_names: list[str]) -> None:
    """Create *username* (and optional groups) if they don't already exist.

    Expects ``init_engine`` to have been called beforehand.
    """
    factory = get_session_factory()
    async with factory() as db:
        # Ensure groups exist
        for name in group_names:
            result = await db.execute(select(Group).where(Group.name == name))
            if not result.scalar_one_or_none():
                db.add(Group(name=name))
                logger.info("Created group '%s'", name)
        await db.flush()

        # Create user or ensure group membership
        result = await db.execute(select(User).where(User.username == username))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            # Ensure the user belongs to all specified groups
            existing_names = {g.name for g in existing_user.groups}
            for name in group_names:
                if name not in existing_names:
                    result = await db.execute(select(Group).where(Group.name == name))
                    existing_user.groups.append(result.scalar_one())
                    logger.info("Added user '%s' to group '%s'", username, name)
        else:
            groups: list[Group] = []
            for name in group_names:
                result = await db.execute(select(Group).where(Group.name == name))
                group = result.scalar_one()
                groups.append(group)

            user = User(
                username=username,
                display_name=username,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                groups=groups,
            )
            db.add(user)
            logger.info("Created user '%s'", username)

        await db.commit()


async def ensure_default_groups(group_names: list[str]) -> None:
    """Create groups if they don't already exist."""
    factory = get_session_factory()
    async with factory() as db:
        for name in group_names:
            result = await db.execute(select(Group).where(Group.name == name))
            if not result.scalar_one_or_none():
                db.add(Group(name=name))
                logger.info("Created default group '%s'", name)
        await db.commit()


def main() -> None:
    """CLI entrypoint — initialises its own engine."""
    from ui.config import AppSettings

    parser = argparse.ArgumentParser(description="Seed users and groups")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--groups", default="", help="Comma-separated group names")
    args = parser.parse_args()

    group_names = [g.strip() for g in args.groups.split(",") if g.strip()]

    async def _run() -> None:
        settings = AppSettings()
        init_engine(settings.database_url)
        try:
            await seed(args.username, args.password, group_names)
        finally:
            await dispose_engine()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
