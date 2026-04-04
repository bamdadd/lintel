"""In-memory retention policy store."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionPolicy:
    """A data retention policy for a given entity type."""

    policy_id: str
    entity_type: str
    max_age_days: int
    action: str  # "delete" or "archive"
    description: str = ""


class InMemoryRetentionPolicyStore:
    """Simple in-memory store for retention policies."""

    def __init__(self) -> None:
        self._policies: dict[str, RetentionPolicy] = {}

    async def add(self, policy: RetentionPolicy) -> None:
        self._policies[policy.policy_id] = policy

    async def get(self, policy_id: str) -> RetentionPolicy | None:
        return self._policies.get(policy_id)

    async def list_all(self) -> list[RetentionPolicy]:
        return list(self._policies.values())

    async def remove(self, policy_id: str) -> None:
        if policy_id not in self._policies:
            msg = f"RetentionPolicy {policy_id} not found"
            raise KeyError(msg)
        del self._policies[policy_id]
