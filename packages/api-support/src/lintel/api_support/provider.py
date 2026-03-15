"""Minimal store provider for dependency injection without dependency-injector."""

from __future__ import annotations

from typing import Any

_UNSET = object()


class StoreProvider:
    """Store holder that can be overridden at app startup.

    Use as a FastAPI ``Depends()`` callable::

        user_store_provider = StoreProvider()

        @router.get("/users")
        async def list_users(
            store = Depends(user_store_provider),
        ):
            ...

    Wire at startup::

        user_store_provider.override(InMemoryUserStore())

    You may also override with ``None`` to signal an optional dependency is not
    configured (the route must check for ``None`` itself).
    """

    def __init__(self) -> None:
        self._instance: Any = _UNSET

    def override(self, instance: Any) -> None:  # noqa: ANN401
        """Set or replace the store instance."""
        self._instance = instance

    def __call__(self) -> Any:  # noqa: ANN401
        """Return the store instance (called by FastAPI Depends)."""
        if self._instance is _UNSET:
            raise RuntimeError("Store not configured — call .override() at app startup")
        return self._instance

    def __class_getitem__(cls, item: Any) -> type:  # noqa: ANN401
        """Allow generic subscript notation e.g. StoreProvider[MyStore]."""
        return cls
