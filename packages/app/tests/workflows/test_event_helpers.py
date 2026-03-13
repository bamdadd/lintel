"""Tests for workflow event helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.contracts.types import AuditEntry

from lintel.workflows.nodes._event_helpers import emit_audit_entry


class _FakeAuditStore:
    """Minimal in-memory audit store for testing."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def add(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class TestEmitAuditEntry:
    async def test_creates_entry_with_correct_fields(self) -> None:
        store = _FakeAuditStore()
        await emit_audit_entry(
            store,
            actor_id="user-1",
            actor_type="user",
            action="workflow_started",
            resource_type="work_item",
            resource_id="wi-123",
            details={"workflow_type": "feature_to_pr"},
        )

        assert len(store.entries) == 1
        entry = store.entries[0]
        assert entry.actor_id == "user-1"
        assert entry.actor_type == "user"
        assert entry.action == "workflow_started"
        assert entry.resource_type == "work_item"
        assert entry.resource_id == "wi-123"
        assert entry.details == {"workflow_type": "feature_to_pr"}
        assert entry.entry_id  # non-empty
        assert entry.timestamp  # non-empty

    async def test_noop_when_store_is_none(self) -> None:
        # Should not raise
        await emit_audit_entry(
            None,
            actor_id="user-1",
            actor_type="user",
            action="workflow_started",
            resource_type="work_item",
            resource_id="wi-123",
        )

    async def test_no_details_defaults_to_none(self) -> None:
        store = _FakeAuditStore()
        await emit_audit_entry(
            store,
            actor_id="sys",
            actor_type="system",
            action="test_action",
            resource_type="thing",
            resource_id="t-1",
        )
        assert store.entries[0].details is None

    async def test_unique_entry_ids(self) -> None:
        store = _FakeAuditStore()
        for _ in range(3):
            await emit_audit_entry(
                store,
                actor_id="a",
                actor_type="system",
                action="x",
                resource_type="r",
                resource_id="id",
            )
        ids = [e.entry_id for e in store.entries]
        assert len(set(ids)) == 3
