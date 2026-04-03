"""In-memory digest stores."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.digest_api.types import Digest, DigestConfig


class InMemoryDigestStore:
    """Simple in-memory store for digests."""

    def __init__(self) -> None:
        self._items: dict[str, Digest] = {}

    async def add(self, digest: Digest) -> None:
        self._items[digest.id] = digest

    async def get(self, digest_id: str) -> Digest | None:
        return self._items.get(digest_id)

    async def list_all(self) -> list[Digest]:
        return list(self._items.values())

    async def remove(self, digest_id: str) -> None:
        del self._items[digest_id]


class InMemoryDigestConfigStore:
    """Simple in-memory store for digest configs."""

    def __init__(self) -> None:
        self._items: dict[str, DigestConfig] = {}

    async def add(self, config: DigestConfig) -> None:
        self._items[config.id] = config

    async def get(self, config_id: str) -> DigestConfig | None:
        return self._items.get(config_id)

    async def list_all(self) -> list[DigestConfig]:
        return list(self._items.values())

    async def update(self, config: DigestConfig) -> None:
        self._items[config.id] = config

    async def remove(self, config_id: str) -> None:
        del self._items[config_id]
