"""Helpers for emitting audit entries and notifications from workflow code."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import uuid4

from lintel.contracts.types import AuditEntry


@runtime_checkable
class _AuditStore(Protocol):
    async def add(self, entry: AuditEntry) -> None: ...


class AuditEmitter:
    """Records audit entries to an audit store."""

    @staticmethod
    async def emit(
        audit_store: _AuditStore | None,
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


# Backward-compatible wrapper
async def emit_audit_entry(
    audit_store: _AuditStore | None,
    *,
    actor_id: str,
    actor_type: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, object] | None = None,
) -> None:
    """Record an audit entry if a store is available.

    Backward-compatible wrapper around :class:`AuditEmitter`.
    """
    await AuditEmitter.emit(
        audit_store,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
