"""NodeDescriptor — metadata describing a workflow stage/node type.

Part of REQ-020: Generalised Workflow Stages. NodeDescriptor is the domain
model that describes what a stage *is* (display name, description, router
type, output edges) without coupling to the handler function.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NodeDescriptor:
    """Describes a registered workflow node type.

    Attributes:
        node_type: Unique identifier matching stage records (e.g. ``"ingest"``).
        display_name: Human-readable name for UI display.
        description: Longer explanation of what this node does.
        router_type: If set, the compiler uses ``RouterFactory.get_router(router_type)``
            to wire conditional edges instead of a plain ``add_edge``.
        output_edges: Possible output edge keys (e.g. ``["continue", "close"]``).
        is_builtin: Whether this node ships with Lintel core.
        tags: Arbitrary classification tags.
    """

    node_type: str
    display_name: str
    description: str = ""
    router_type: str | None = None
    output_edges: tuple[str, ...] = ()
    is_builtin: bool = True
    tags: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
