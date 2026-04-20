"""Configuration dataclasses for GenericTableView."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Column:
    """A column in the table view."""

    key: str  # Field name on the Pydantic display model
    label: str  # Header text
    css_class: str = ""  # e.g. "hidden sm:table-cell" for responsive hiding
    sortable: bool = False  # Whether this column can be sorted
    sort_field: str = ""  # ORM column name for sorting (defaults to key if empty)
    render: str | None = None  # Jinja2 macro name for custom cell rendering


@dataclass
class SortOption:
    """A sort option shown in the sort dropdown."""

    value: str  # "field:direction", e.g. "created_at:desc"
    label: str  # "Newest first"


@dataclass
class TabConfig:
    """Tab bar configuration for status-based filtering."""

    order: list[str]  # Tab keys in display order, e.g. ["open", "completed", "all"]
    labels: dict[str, str]  # Tab key → display label
    status_field: str = "status"  # ORM column name used for tab filtering
    default_tab: str = ""  # Falls back to order[0] if empty
    status_groups: dict[str, list[str]] = field(default_factory=dict)
    # Maps a tab key to multiple DB status values, e.g. {"running": ["starting", "running"]}


@dataclass
class FilterDef:
    """A named filter dropdown (simple select-style)."""

    key: str  # Query param name, e.g. "type", "priority"
    label: str  # Button label, e.g. "Priority"
    field: str = ""  # ORM column name; defaults to key if empty


@dataclass
class QueryField:
    """A field available in the advanced query builder."""

    key: str  # ORM column name
    label: str  # Human-readable label
    field_type: str  # "string", "number", "date", "enum"
    enum_values: list[str] = field(default_factory=list)  # For enum-type fields
