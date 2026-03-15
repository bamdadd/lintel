"""Dependency injection providers for the memory API."""

from lintel.api_support.provider import StoreProvider
from lintel.memory.memory_service import MemoryService

memory_service_provider: StoreProvider[MemoryService] = StoreProvider()
