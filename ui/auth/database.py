"""Backwards-compatibility shim — canonical location is core.db.engine."""
from core.db.engine import dispose_engine, get_session_factory, init_engine  # noqa: F401
