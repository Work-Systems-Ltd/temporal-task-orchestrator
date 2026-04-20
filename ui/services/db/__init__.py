"""Backwards-compatibility shim — canonical location is core.db."""
from core.db.service import DbService  # noqa: F401

__all__ = ["DbService"]
