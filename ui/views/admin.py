"""Admin table views — users and groups powered by GenericTableView."""
from __future__ import annotations

from fastapi import Request

from core.db import DbService, Group, User
from ui.helpers import relative_time
from ui.models import GroupListItem, UserListItem

from .table_view import GenericTableView
from .types import QueryField, SortOption, TabConfig


def _format_dt(dt) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserTableView(GenericTableView[User, UserListItem]):
    model_class = User
    serializer_class = UserListItem
    template = "admin/users.html"
    url_prefix = "/admin/users"
    page_title = "Users"
    route_name = "admin_users_page"

    tabs = TabConfig(
        order=["all"],
        labels={"all": "All"},
        default_tab="all",
    )

    sort_options = [
        SortOption("username:asc", "Username A-Z"),
        SortOption("username:desc", "Username Z-A"),
        SortOption("created_at:desc", "Newest first"),
        SortOption("created_at:asc", "Oldest first"),
    ]

    query_fields = [
        QueryField("username", "Username", "string"),
        QueryField("display_name", "Display Name", "string"),
        QueryField("is_active", "Active", "enum", enum_values=["true", "false"]),
        QueryField("created_at", "Created", "date"),
    ]

    search_fields = ["username", "display_name"]
    default_sort = "username"
    default_order = "asc"

    def convert_record(self, record: User) -> UserListItem:
        return UserListItem(
            record_id=str(record.id),
            username=record.username,
            display_name=record.display_name if record.display_name != record.username else "",
            slug=record.slug,
            is_active=record.is_active,
            groups=", ".join(g.name for g in record.groups),
            group_count=len(record.groups),
            created_at=_format_dt(record.created_at),
        )

    async def get_tab_counts(self, request: Request, db: DbService) -> dict[str, int]:
        total = await db.count_users()
        return {"all": total}

    async def get_extra_context(self, request: Request, db: DbService) -> dict:
        # Pass all groups for the modals (add user, manage groups)
        all_groups = await db.list_groups()
        return {"all_groups": all_groups}


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


class GroupTableView(GenericTableView[Group, GroupListItem]):
    model_class = Group
    serializer_class = GroupListItem
    template = "admin/groups.html"
    url_prefix = "/admin/groups"
    page_title = "Groups"
    route_name = "admin_groups_page"

    tabs = TabConfig(
        order=["all"],
        labels={"all": "All"},
        default_tab="all",
    )

    sort_options = [
        SortOption("name:asc", "Name A-Z"),
        SortOption("name:desc", "Name Z-A"),
        SortOption("created_at:desc", "Newest first"),
        SortOption("created_at:asc", "Oldest first"),
    ]

    query_fields = [
        QueryField("name", "Name", "string"),
        QueryField("created_at", "Created", "date"),
    ]

    search_fields = ["name"]
    default_sort = "name"
    default_order = "asc"

    def convert_record(self, record: Group) -> GroupListItem:
        return GroupListItem(
            record_id=str(record.id),
            name=record.name,
            slug=record.slug,
            member_count=len(record.users),
            members=", ".join(u.username for u in record.users),
            created_at=_format_dt(record.created_at),
        )

    async def get_tab_counts(self, request: Request, db: DbService) -> dict[str, int]:
        total = await db.count_groups()
        return {"all": total}
