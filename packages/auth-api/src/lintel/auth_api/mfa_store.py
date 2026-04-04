"""In-memory MFA configuration store."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.auth.types import MFAConfig, MFAMethod


class InMemoryMFAStore:
    """In-memory store for MFA configs, keyed by (user_id, method)."""

    def __init__(self) -> None:
        self._configs: dict[tuple[str, str], MFAConfig] = {}

    async def save(self, config: MFAConfig) -> None:
        self._configs[(config.user_id, config.method)] = config

    async def get(self, user_id: str, method: MFAMethod) -> MFAConfig | None:
        return self._configs.get((user_id, method))

    async def enable(self, user_id: str, method: MFAMethod) -> bool:
        key = (user_id, method)
        cfg = self._configs.get(key)
        if cfg is None:
            return False
        self._configs[key] = replace(cfg, enabled=True)
        return True

    async def list_for_user(self, user_id: str) -> list[MFAConfig]:
        return [c for c in self._configs.values() if c.user_id == user_id]
