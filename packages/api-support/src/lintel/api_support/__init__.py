"""Shared API support utilities for extracted route packages.

Public API surface:

- ``StoreProvider[T]`` — lazy dependency holder for FastAPI ``Depends()``
- ``EntityStore[T]`` — protocol for typed entity stores
- ``DictStore`` — protocol for plain dict stores
- ``ProjectScopedDictStore`` — DictStore with project-scoped listing
- ``dispatch_event`` — fire-and-forget helper for publishing domain events
- ``dispatch_event_raw`` — same as above but accepts ``app.state`` directly
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
