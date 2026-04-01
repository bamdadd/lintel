"""NodeRegistry — maps node_type strings to (descriptor, handler) pairs.

Module-level singleton ``node_registry`` is the canonical instance used by
the compiler and stage-catalogue API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from lintel.workflows.node_descriptor import NodeDescriptor


class NodeRegistry:
    """In-memory registry of workflow node types."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[NodeDescriptor, Callable[..., Any]]] = {}

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def register(self, descriptor: NodeDescriptor, handler_fn: Callable[..., Any]) -> None:
        """Register a node type with its descriptor and handler function."""
        self._entries[descriptor.node_type] = (descriptor, handler_fn)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, node_type: str) -> tuple[NodeDescriptor, Callable[..., Any]]:
        """Return ``(descriptor, handler_fn)`` for *node_type*.

        Raises:
            KeyError: If *node_type* is not registered.
        """
        try:
            return self._entries[node_type]
        except KeyError:
            registered = ", ".join(sorted(self._entries)) or "(none)"
            msg = f"Unknown node_type {node_type!r}. Registered types: {registered}"
            raise KeyError(msg) from None

    def list_all(self) -> list[NodeDescriptor]:
        """Return all registered descriptors (sorted by node_type)."""
        return [desc for desc, _ in sorted(self._entries.values(), key=lambda t: t[0].node_type)]

    def __contains__(self, node_type: str) -> bool:
        return node_type in self._entries

    def __len__(self) -> int:
        return len(self._entries)


#: Module-level singleton instance.
node_registry = NodeRegistry()
