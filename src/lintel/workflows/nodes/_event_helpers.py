"""Helpers for emitting audit entries and notifications from workflow code."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from lintel.contracts.types import AuditEntry


async def emit_audit_entry(
    audit_store: object | None,
    *,
    actor_id: str,
    actor_type: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, object] | None = None,
) -> None:
    """Record an audit entry if a store is available."""
    if audit_store is None:
        return
    entry = AuditEntry(
        entry_id=uuid4().hex,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        timestamp=datetime.now(UTC).isoformat(),
    )
    await audit_store.add(entry)
