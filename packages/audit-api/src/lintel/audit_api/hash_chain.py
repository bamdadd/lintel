"""Tamper-proof hash chain audit store with verification and export."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from lintel.audit_api.store import AuditEntryStore
from lintel.domain.types import AuditEntry


@dataclass(frozen=True)
class ChainVerificationResult:
    """Result of verifying the audit hash chain."""

    valid: bool
    entries_checked: int
    broken_at: str | None = None


class HashChainAuditStore:
    """Append-only audit store with SHA-256 hash chain for tamper detection.

    Each entry stores the hash of the previous entry. Verification walks the
    chain and recomputes hashes to detect any modifications.
    """

    GENESIS_HASH = "0" * 64  # SHA-256 zero hash for first entry

    def __init__(self) -> None:
        self._inner = AuditEntryStore()
        self._chain: list[AuditEntry] = []
        self._last_hash: str = self.GENESIS_HASH

    @staticmethod
    def compute_hash(entry: AuditEntry) -> str:
        """Compute SHA-256 hash of an audit entry's content."""
        data = asdict(entry)
        # Exclude previous_hash from the hash computation to avoid circularity
        data.pop("previous_hash", None)
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def add(self, entry: AuditEntry) -> None:
        """Append entry with hash chain linking to the previous entry."""
        chained = AuditEntry(
            entry_id=entry.entry_id,
            actor_id=entry.actor_id,
            actor_type=entry.actor_type,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            details=entry.details,
            timestamp=entry.timestamp,
            previous_hash=self._last_hash,
        )
        await self._inner.add(chained)
        self._chain.append(chained)
        self._last_hash = self.compute_hash(chained)

    async def get(self, entry_id: str) -> AuditEntry | None:
        return await self._inner.get(entry_id)

    async def list_all(
        self,
        *,
        actor_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> list[AuditEntry]:
        return await self._inner.list_all(
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    async def verify_chain(self) -> ChainVerificationResult:
        """Walk the chain and verify each entry's hash against the next."""
        if not self._chain:
            return ChainVerificationResult(valid=True, entries_checked=0)

        prev_hash = self.GENESIS_HASH
        for entry in self._chain:
            if entry.previous_hash != prev_hash:
                return ChainVerificationResult(
                    valid=False,
                    entries_checked=len(self._chain),
                    broken_at=entry.entry_id,
                )
            prev_hash = self.compute_hash(entry)

        return ChainVerificationResult(
            valid=True,
            entries_checked=len(self._chain),
        )

    async def export_entries(
        self,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ) -> list[AuditEntry]:
        """Export entries optionally filtered by timestamp range."""
        entries = list(self._chain)
        if from_ts is not None:
            entries = [e for e in entries if e.timestamp >= from_ts]
        if to_ts is not None:
            entries = [e for e in entries if e.timestamp <= to_ts]
        return entries
