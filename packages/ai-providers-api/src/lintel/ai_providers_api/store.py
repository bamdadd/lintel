"""In-memory store for AI provider configurations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.models.types import AIProvider


class InMemoryAIProviderStore:
    """In-memory store for AI provider configurations."""

    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}
        self._api_keys: dict[str, str] = {}

    async def add(self, provider: AIProvider, api_key: str = "") -> None:
        self._providers[provider.provider_id] = provider
        if api_key:
            self._api_keys[provider.provider_id] = api_key

    async def get(self, provider_id: str) -> AIProvider | None:
        return self._providers.get(provider_id)

    async def list_all(self) -> list[AIProvider]:
        return list(self._providers.values())

    async def update(self, provider: AIProvider) -> None:
        if provider.provider_id not in self._providers:
            msg = f"Provider {provider.provider_id} not found"
            raise KeyError(msg)
        self._providers[provider.provider_id] = provider

    async def update_api_key(self, provider_id: str, api_key: str) -> None:
        if provider_id not in self._providers:
            msg = f"Provider {provider_id} not found"
            raise KeyError(msg)
        self._api_keys[provider_id] = api_key

    async def remove(self, provider_id: str) -> None:
        if provider_id not in self._providers:
            msg = f"Provider {provider_id} not found"
            raise KeyError(msg)
        del self._providers[provider_id]
        self._api_keys.pop(provider_id, None)

    async def has_api_key(self, provider_id: str) -> bool:
        return bool(self._api_keys.get(provider_id))

    async def get_default(self) -> AIProvider | None:
        for p in self._providers.values():
            if p.is_default:
                return p
        return None
