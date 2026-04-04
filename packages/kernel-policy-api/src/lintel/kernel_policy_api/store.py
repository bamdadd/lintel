"""In-memory kernel policy store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.kernel_policy_api.types import KernelPolicy


class InMemoryKernelPolicyStore:
    """Simple in-memory store for kernel policies."""

    def __init__(self) -> None:
        self._policies: dict[str, KernelPolicy] = {}

    async def add(self, policy: KernelPolicy) -> None:
        self._policies[policy.policy_id] = policy

    async def get(self, policy_id: str) -> KernelPolicy | None:
        return self._policies.get(policy_id)

    async def list_all(self) -> list[KernelPolicy]:
        return list(self._policies.values())

    async def update(self, policy: KernelPolicy) -> None:
        self._policies[policy.policy_id] = policy

    async def remove(self, policy_id: str) -> None:
        del self._policies[policy_id]
