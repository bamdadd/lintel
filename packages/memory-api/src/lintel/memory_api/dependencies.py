"""Dependency injection providers for the memory API."""

from typing import Any

from lintel.api_support.provider import StoreProvider

memory_service_provider: StoreProvider[Any] = StoreProvider()
