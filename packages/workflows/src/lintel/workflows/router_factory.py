"""RouterFactory — maps router_type strings to conditional-edge callables.

Each router function must match LangGraph's ``(state) -> str`` signature.
Module-level singleton ``router_factory`` is used by the compiler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class RouterFactory:
    """In-memory registry of conditional-edge router functions."""

    def __init__(self) -> None:
        self._routers: dict[str, Callable[[dict[str, Any]], str]] = {}

    def register_router(
        self,
        router_type: str,
        fn: Callable[[dict[str, Any]], str],
    ) -> None:
        """Register a router function for *router_type*."""
        self._routers[router_type] = fn

    def get_router(self, router_type: str) -> Callable[[dict[str, Any]], str]:
        """Return the router callable for *router_type*.

        Raises:
            KeyError: If *router_type* is not registered.
        """
        try:
            return self._routers[router_type]
        except KeyError:
            registered = ", ".join(sorted(self._routers)) or "(none)"
            msg = f"Unknown router_type {router_type!r}. Registered routers: {registered}"
            raise KeyError(msg) from None

    def list_all(self) -> list[str]:
        """Return all registered router type names."""
        return sorted(self._routers)

    def __contains__(self, router_type: str) -> bool:
        return router_type in self._routers

    def __len__(self) -> int:
        return len(self._routers)


#: Module-level singleton instance.
router_factory = RouterFactory()
