"""GraphCompiler — compiles visual editor graph definitions into executable StateGraphs."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from langgraph.graph import StateGraph

if TYPE_CHECKING:
    from collections.abc import Callable

    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph


class ThreadWorkflowState(TypedDict, total=False):
    """Minimal state schema for compiled workflows."""

    thread_ref: str
    correlation_id: str
    output: dict[str, object]


class GraphCompiler:
    """Compiles stored {nodes, edges} from visual editor into executable StateGraph."""

    def __init__(self, node_registry: dict[str, object]) -> None:
        self._registry = node_registry

    def compile(
        self,
        definition: object,
        checkpointer: BaseCheckpointSaver | None,
    ) -> CompiledStateGraph:
        graph_data = definition.graph  # type: ignore[attr-defined]
        builder = StateGraph(ThreadWorkflowState)

        for node in graph_data["nodes"]:
            node_fn = self._resolve_node_function(node)
            builder.add_node(node["id"], node_fn)

        for edge in graph_data["edges"]:
            if edge["source"] == "__start__":
                builder.set_entry_point(edge["target"])
            else:
                builder.add_edge(edge["source"], edge["target"])

        approval_nodes = [
            n["id"] for n in graph_data["nodes"] if n["type"] == "approvalGate"
        ]

        return builder.compile(
            checkpointer=checkpointer,
            interrupt_before=approval_nodes or None,
        )

    def _resolve_node_function(self, node: dict[str, str]) -> Callable[..., object]:
        key = f"{node['type']}:{node.get('role', '')}"
        fn = self._registry.get(key)
        if fn is None:
            msg = f"No handler registered for node type '{key}'"
            raise ValueError(msg)
        return fn  # type: ignore[return-value]
