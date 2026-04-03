"""Tests for tamper-proof hash chain audit store."""

from __future__ import annotations

from lintel.audit_api.hash_chain import HashChainAuditStore
from lintel.domain.types import AuditEntry


def _entry(entry_id: str, action: str = "create", ts: str = "") -> AuditEntry:
    return AuditEntry(
        entry_id=entry_id,
        actor_id="u-1",
        actor_type="user",
        action=action,
        resource_type="project",
        resource_id="proj-1",
        timestamp=ts,
    )


class TestHashChainAuditStore:
    async def test_add_sets_previous_hash_on_first_entry(self) -> None:
        store = HashChainAuditStore()
        await store.add(_entry("a-1"))
        entry = await store.get("a-1")
        assert entry is not None
        assert entry.previous_hash is not None
        # First entry chains from the genesis hash
        assert entry.previous_hash == HashChainAuditStore.GENESIS_HASH

    async def test_add_chains_hashes_across_entries(self) -> None:
        store = HashChainAuditStore()
        await store.add(_entry("a-1"))
        await store.add(_entry("a-2"))
        e1 = await store.get("a-1")
        e2 = await store.get("a-2")
        assert e1 is not None and e2 is not None
        assert e2.previous_hash != e1.previous_hash
        # e2's previous_hash should be the hash of e1
        assert e2.previous_hash == store.compute_hash(e1)

    async def test_verify_chain_valid(self) -> None:
        store = HashChainAuditStore()
        await store.add(_entry("a-1", ts="2025-01-01T00:00:00"))
        await store.add(_entry("a-2", ts="2025-01-01T00:01:00"))
        await store.add(_entry("a-3", ts="2025-01-01T00:02:00"))
        result = await store.verify_chain()
        assert result.valid is True
        assert result.entries_checked == 3
        assert result.broken_at is None

    async def test_verify_chain_detects_tampering(self) -> None:
        store = HashChainAuditStore()
        await store.add(_entry("a-1", ts="2025-01-01T00:00:00"))
        await store.add(_entry("a-2", ts="2025-01-01T00:01:00"))
        # Tamper with the first entry by mutating the backing store
        tampered = AuditEntry(
            entry_id="a-1",
            actor_id="HACKER",
            actor_type="user",
            action="create",
            resource_type="project",
            resource_id="proj-1",
            timestamp="2025-01-01T00:00:00",
            previous_hash=store._chain[0].previous_hash,
        )
        store._chain[0] = tampered
        store._inner._entries["a-1"] = tampered
        result = await store.verify_chain()
        assert result.valid is False
        assert result.broken_at == "a-2"

    async def test_verify_empty_chain(self) -> None:
        store = HashChainAuditStore()
        result = await store.verify_chain()
        assert result.valid is True
        assert result.entries_checked == 0

    async def test_list_all_delegates(self) -> None:
        store = HashChainAuditStore()
        await store.add(_entry("a-1"))
        await store.add(_entry("a-2"))
        entries = await store.list_all()
        assert len(entries) == 2

    async def test_list_all_filters(self) -> None:
        store = HashChainAuditStore()
        e1 = AuditEntry(
            entry_id="a-1",
            actor_id="u-1",
            actor_type="user",
            action="create",
            resource_type="project",
            resource_id="proj-1",
        )
        e2 = AuditEntry(
            entry_id="a-2",
            actor_id="u-2",
            actor_type="user",
            action="delete",
            resource_type="team",
            resource_id="team-1",
        )
        await store.add(e1)
        await store.add(e2)
        entries = await store.list_all(actor_id="u-1")
        assert len(entries) == 1
        assert entries[0].entry_id == "a-1"

    async def test_export_json(self) -> None:
        store = HashChainAuditStore()
        await store.add(_entry("a-1", ts="2025-01-01T00:00:00"))
        await store.add(_entry("a-2", ts="2025-01-02T00:00:00"))
        result = await store.export_entries(
            from_ts="2025-01-01T00:00:00",
            to_ts="2025-01-02T00:00:00",
        )
        assert len(result) == 2

    async def test_export_filters_by_date(self) -> None:
        store = HashChainAuditStore()
        await store.add(_entry("a-1", ts="2025-01-01T00:00:00"))
        await store.add(_entry("a-2", ts="2025-01-05T00:00:00"))
        await store.add(_entry("a-3", ts="2025-01-10T00:00:00"))
        result = await store.export_entries(
            from_ts="2025-01-02T00:00:00",
            to_ts="2025-01-06T00:00:00",
        )
        assert len(result) == 1
        assert result[0].entry_id == "a-2"
