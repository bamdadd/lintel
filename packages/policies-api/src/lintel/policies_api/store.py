"""In-memory policy store."""

from lintel.domain.types import Policy


class InMemoryPolicyStore:
    """Simple in-memory store for policies."""

    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}

    async def add(self, policy: Policy) -> None:
        self._policies[policy.policy_id] = policy

    async def get(self, policy_id: str) -> Policy | None:
        return self._policies.get(policy_id)

    async def list_all(self) -> list[Policy]:
        return list(self._policies.values())

    async def list_by_project(self, project_id: str) -> list[Policy]:
        return [p for p in self._policies.values() if p.project_id == project_id]

    async def update(self, policy: Policy) -> None:
        self._policies[policy.policy_id] = policy

    async def remove(self, policy_id: str) -> None:
        del self._policies[policy_id]
