"""In-memory store for SSO provider configurations and login states."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.auth.sso import SSOLoginRequest, SSOProviderConfig


class InMemorySSOConfigStore:
    """In-memory store for SSO provider configurations, keyed by config_id."""

    def __init__(self) -> None:
        self._configs: dict[str, SSOProviderConfig] = {}

    async def save(self, config: SSOProviderConfig) -> None:
        self._configs[config.config_id] = config

    async def get(self, config_id: str) -> SSOProviderConfig | None:
        return self._configs.get(config_id)

    async def list_all(self) -> list[SSOProviderConfig]:
        return list(self._configs.values())

    async def delete(self, config_id: str) -> bool:
        return self._configs.pop(config_id, None) is not None


class InMemorySSOStateStore:
    """In-memory store for pending SSO login states (state token → request)."""

    def __init__(self) -> None:
        self._states: dict[str, SSOLoginRequest] = {}

    async def save(self, req: SSOLoginRequest) -> None:
        self._states[req.state] = req

    async def pop(self, state: str) -> SSOLoginRequest | None:
        """Retrieve and remove a pending login request by state token."""
        return self._states.pop(state, None)
