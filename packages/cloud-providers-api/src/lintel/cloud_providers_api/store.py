"""In-memory store for cloud providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.cloud_providers_api.types import CloudProvider


class InMemoryCloudProviderStore:
    """Simple in-memory store for cloud providers."""

    def __init__(self) -> None:
        self._data: dict[str, CloudProvider] = {}

    async def add(self, provider: CloudProvider) -> None:
        self._data[provider.id] = provider

    async def get(self, provider_id: str) -> CloudProvider | None:
        return self._data.get(provider_id)

    async def list_all(self) -> list[CloudProvider]:
        return list(self._data.values())

    async def delete(self, provider_id: str) -> bool:
        return self._data.pop(provider_id, None) is not None
