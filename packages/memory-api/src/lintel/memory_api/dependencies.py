"""Dependency injection providers for the memory API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.memory.memory_service import MemoryService

memory_service_provider: StoreProvider[MemoryService] = StoreProvider()
