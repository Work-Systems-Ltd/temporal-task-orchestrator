"""Parse advanced filter query params into SQLAlchemy conditions.

URL format: filter=field:op:value (multi-valued)
Operators: eq, ne, contains, startswith, in, gt, lt, gte, lte, null, notnull
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_

from .types import QueryField

# Operator → lambda(column, value) → SQLAlchemy condition
_OPERATORS: dict[str, Any] = {
    "eq": lambda col, val: col == val,
    "ne": lambda col, val: col != val,
    "contains": lambda col, val: col.ilike(f"%{val}%"),
    "startswith": lambda col, val: col.ilike(f"{val}%"),
    "in": lambda col, val: col.in_(val.split(",")),
    "gt": lambda col, val: col > val,
    "lt": lambda col, val: col < val,
    "gte": lambda col, val: col >= val,
    "lte": lambda col, val: col <= val,
    "null": lambda col, _val: col.is_(None),
    "notnull": lambda col, _val: col.isnot(None),
}


def _coerce_value(value: str, field_type: str) -> Any:
    """Coerce a string value to the appropriate Python type."""
    if field_type == "number":
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value
    if field_type == "date":
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return value
    return value


def parse_filters(
    filter_params: list[str],
    model_class: type,
    query_fields: list[QueryField],
    logic: str = "and",
) -> list:
    """Parse filter= query params and return a list of SQLAlchemy conditions.

    Args:
        filter_params: Raw filter strings, e.g. ["priority:eq:high", "status:ne:closed"]
        model_class: SQLAlchemy ORM model class
        query_fields: Allowed fields for filtering
        logic: "and" or "or" — how to combine conditions (applied by caller)

    Returns:
        List of SQLAlchemy column expressions. Caller applies AND/OR.
    """
    allowed = {qf.key: qf for qf in query_fields}
    conditions = []

    for param in filter_params:
        parts = param.split(":", 2)
        if len(parts) < 2:
            continue

        field_name = parts[0]
        op = parts[1]
        value = parts[2] if len(parts) > 2 else ""

        if field_name not in allowed:
            continue
        if op not in _OPERATORS:
            continue

        col = getattr(model_class, field_name, None)
        if col is None:
            continue

        qf = allowed[field_name]

        # Coerce value for typed operators
        if op not in ("null", "notnull", "in"):
            value = _coerce_value(value, qf.field_type)

        conditions.append(_OPERATORS[op](col, value))

    return conditions
