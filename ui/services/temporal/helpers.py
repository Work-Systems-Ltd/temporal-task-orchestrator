"""Pure helper functions with no Temporal client dependency."""

from __future__ import annotations

from datetime import datetime, timedelta


def ms_duration(start: datetime, end: datetime) -> str:
    """Format a duration between two datetimes as a human-readable string."""
    diff = (end - start).total_seconds()
    if diff < 0.001:
        return "<1ms"
    if diff < 1:
        return f"{int(diff * 1000)}ms"
    if diff < 60:
        return f"{diff:.1f}s"
    minutes = int(diff) // 60
    secs = int(diff) % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"


def duration_from_secs(seconds: float) -> str:
    """Format a number of seconds as a human-readable duration string."""
    if seconds <= 0:
        return "—"
    epoch = datetime.min.replace(tzinfo=None)
    return ms_duration(epoch, epoch + timedelta(seconds=seconds))


def build_query(base_query: str | None, wf_type: str | None) -> str | None:
    """Combine a base Temporal visibility query with an optional workflow type filter."""
    parts: list[str] = []
    if base_query:
        parts.append(base_query)
    if wf_type:
        parts.append(f'WorkflowType="{wf_type}"')
    return " AND ".join(parts) if parts else None


def is_assigned_to_user(
    assigned_user: str,
    assigned_group: str,
    user_slug: str,
    group_slugs: list[str],
) -> bool:
    """Check if a task is accessible to the given user or any of their groups."""
    if not assigned_user and not assigned_group:
        return True  # unassigned → visible to everyone
    if assigned_user and assigned_user == user_slug:
        return True
    if assigned_group and assigned_group in group_slugs:
        return True
    return False


def group_by_parent(items: list) -> list:
    """Group child workflows under their parents.

    Uses the authoritative parent_id field from Temporal (populated by
    WorkflowExecution.parent_id). Falls back to ID convention
    ({parent_id}-{suffix}) if parent_id is empty but a matching parent
    exists in the list.
    """
    by_id = {item.workflow_id: item for item in items}
    children_ids: set[str] = set()

    for item in items:
        pid = getattr(item, "parent_id", "") or ""
        if pid and pid in by_id:
            by_id[pid].children.append(item.model_dump())
            children_ids.add(item.workflow_id)
            continue

        # Fallback: ID convention (e.g., "hiring-123-approval" → parent "hiring-123")
        parts = item.workflow_id.rsplit("-", 1)
        if len(parts) == 2:
            potential_parent = parts[0]
            if potential_parent in by_id and potential_parent != item.workflow_id:
                by_id[potential_parent].children.append(item.model_dump())
                item.parent_id = potential_parent
                children_ids.add(item.workflow_id)

    return [item for item in items if item.workflow_id not in children_ids]
