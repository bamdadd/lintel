"""Minimal store provider for dependency injection without dependency-injector."""

from __future__ import annotations

from typing import Any


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
    """

    def __init__(self) -> None:
        self._instance: Any = None

    def override(self, instance: Any) -> None:  # noqa: ANN401
        """Set or replace the store instance."""
        self._instance = instance

    def __call__(self) -> Any:  # noqa: ANN401
        """Return the store instance (called by FastAPI Depends)."""
        if self._instance is None:
            raise RuntimeError("Store not configured — call .override() at app startup")
        return self._instance
