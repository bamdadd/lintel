"""Shared API support utilities for extracted route packages.

Public surface:

- ``StoreProvider[T]`` — lightweight DI holder for store instances
- ``EntityStore[T]`` — Protocol for typed entity CRUD stores
- ``DictStore`` — Protocol for plain-dict CRUD stores
- ``ProjectScopedDictStore`` — DictStore with project-scoped listing
- ``dispatch_event`` / ``dispatch_event_raw`` — fire-and-forget event publishing
"""

from lintel.api_support.event_dispatcher import dispatch_event, dispatch_event_raw
from lintel.api_support.protocols import DictStore, EntityStore, ProjectScopedDictStore
from lintel.api_support.provider import StoreProvider

__all__ = [
    "DictStore",
    "EntityStore",
    "ProjectScopedDictStore",
    "StoreProvider",
    "dispatch_event",
    "dispatch_event_raw",
]
