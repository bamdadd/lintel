"""In-memory stores for secret rotation policies and rotation history."""

from __future__ import annotations

from datetime import UTC, datetime


class InMemoryRotationPolicyStore:
    """In-memory rotation policy store."""

    def __init__(self) -> None:
        self._policies: dict[str, dict[str, object]] = {}

    async def create(self, data: dict[str, object]) -> dict[str, object]:
        policy_id = str(data["policy_id"])
        self._policies[policy_id] = data
        return data

    async def get(self, policy_id: str) -> dict[str, object] | None:
        return self._policies.get(policy_id)

    async def list_all(self) -> list[dict[str, object]]:
        return list(self._policies.values())

    async def delete(self, policy_id: str) -> bool:
        return self._policies.pop(policy_id, None) is not None


class InMemoryRotationHistoryStore:
    """In-memory rotation history store."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, object]] = {}

    async def record(self, data: dict[str, object]) -> dict[str, object]:
        entry_id = str(data["entry_id"])
        self._entries[entry_id] = data
        return data

    async def list_by_credential(self, credential_id: str) -> list[dict[str, object]]:
        return [e for e in self._entries.values() if e.get("credential_id") == credential_id]

    async def list_all(self) -> list[dict[str, object]]:
        return list(self._entries.values())


class InMemoryExpiryTracker:
    """Tracks credential expiry dates for alerting."""

    def __init__(self) -> None:
        self._expiry: dict[str, dict[str, object]] = {}

    async def set_expiry(
        self,
        credential_id: str,
        expires_at: str,
        policy_id: str | None = None,
    ) -> None:
        self._expiry[credential_id] = {
            "credential_id": credential_id,
            "expires_at": expires_at,
            "policy_id": policy_id,
        }

    async def get_expiry(self, credential_id: str) -> dict[str, object] | None:
        return self._expiry.get(credential_id)

    async def list_expiring_before(self, before: str) -> list[dict[str, object]]:
        """Return credentials expiring before the given ISO timestamp."""
        cutoff = datetime.fromisoformat(before).replace(tzinfo=UTC)
        results: list[dict[str, object]] = []
        for entry in self._expiry.values():
            exp_str = str(entry["expires_at"])
            exp_dt = datetime.fromisoformat(exp_str).replace(tzinfo=UTC)
            if exp_dt <= cutoff:
                results.append(entry)
        return results
