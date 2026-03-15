"""Minimal store provider for dependency injection without dependency-injector."""

from __future__ import annotations

from typing import Any

_UNSET = object()


class StoreProvider[T]:
    """Store holder that can be overridden at app startup.

    Use as a FastAPI ``Depends()`` callable::

        user_store_provider: StoreProvider[MyStore] = StoreProvider()

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

    def override(self, instance: T) -> None:
        """Set or replace the store instance."""
        self._instance = instance

    def reset(self) -> None:
        """Reset to unconfigured state."""
        self._instance = _UNSET

    def get(self) -> T:
        """Return the store instance."""
        if self._instance is _UNSET:
            raise RuntimeError("Store not configured — call .override() at app startup")
        return self._instance  # type: ignore[return-value]

    def __call__(self) -> T:
        """Return the store instance (called by FastAPI Depends)."""
        return self.get()
