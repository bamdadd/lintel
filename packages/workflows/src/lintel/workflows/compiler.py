"""LangGraphCompiler — data-driven StateGraph construction from WorkflowDefinitionRecord.

Replaces hardcoded graph builders by reading stage/edge information from
the definition record and wiring nodes dynamically via NodeRegistry +
RouterFactory lookups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from lintel.workflows.state import ThreadWorkflowState

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable

    from langgraph.graph.state import CompiledStateGraph

    from lintel.workflows.node_registry import NodeRegistry
    from lintel.workflows.router_factory import RouterFactory
    from lintel.workflows.types import WorkflowDefinitionRecord


class LangGraphCompiler:
    """Build a LangGraph ``StateGraph`` from a ``WorkflowDefinitionRecord``."""

    def compile(
        self,
        definition: WorkflowDefinitionRecord,
        registry: NodeRegistry,
        router_factory: RouterFactory,
        checkpointer: Any = None,  # noqa: ANN401
    ) -> CompiledStateGraph[Any]:
        """Compile *definition* into an executable ``CompiledStateGraph``.

        Args:
            definition: The workflow template describing nodes, edges, and
                conditional edges.
            registry: Maps ``node_type`` strings to handler callables.
            router_factory: Maps ``router_type`` strings to conditional-edge
                callables.
            checkpointer: Optional LangGraph checkpointer for persistence.

        Returns:
            A compiled state graph ready for execution.

        Raises:
            KeyError: If any ``node_type`` in the definition is not registered.
        """
        graph: StateGraph[Any] = StateGraph(ThreadWorkflowState)

        # --- Add nodes ---
        for node_name in definition.graph_nodes:
            _descriptor, handler_fn = registry.get(node_name)
            graph.add_node(node_name, handler_fn)

        # --- Set entry point ---
        if definition.entry_point:
            graph.set_entry_point(definition.entry_point)
        elif definition.graph_nodes:
            graph.set_entry_point(definition.graph_nodes[0])

        # --- Build a set of nodes that are conditional-edge *sources* ---
        conditional_sources: set[str] = set()
        for cond in definition.conditional_edges:
            source = str(cond.get("source", ""))
            if source:
                conditional_sources.add(source)

        # --- Add plain edges ---
        for source, target in definition.graph_edges:
            # Skip edges whose source is handled by conditional_edges
            if source in conditional_sources:
                continue
            if target == "__end__":
                graph.add_edge(source, END)
            else:
                graph.add_edge(source, target)

        # --- Add conditional edges ---
        for cond in definition.conditional_edges:
            source = str(cond.get("source", ""))
            targets_raw = cond.get("targets", {})
            router_type = str(cond.get("router_type", ""))

            if not source or not targets_raw:
                continue

            # Build target map, replacing __end__ with END sentinel
            targets: dict[Hashable, str] = {}
            for key, val in (targets_raw if isinstance(targets_raw, dict) else {}).items():
                targets[key] = str(val)

            # Resolve router function
            router_fn: Callable[..., str]
            if router_type:
                router_fn = router_factory.get_router(router_type)
            else:
                # Try to find the router from the node descriptor
                if source in registry:
                    desc, _ = registry.get(source)
                    if desc.router_type:
                        router_fn = router_factory.get_router(desc.router_type)
                    else:
                        # Fallback: first target value as default
                        _default = next(iter(targets.values()))
                        router_fn = lambda _s, _t=_default: _t  # noqa: E731
                else:
                    _default = next(iter(targets.values()))
                    router_fn = lambda _s, _t=_default: _t  # noqa: E731

            graph.add_conditional_edges(source, router_fn, targets)

        # --- Wire terminal node to END if not already connected ---
        if definition.graph_nodes:
            last_node = definition.graph_nodes[-1]
            # Check if last node already has an outgoing edge
            has_outgoing = any(s == last_node for s, _ in definition.graph_edges)
            has_conditional = last_node in conditional_sources
            if not has_outgoing and not has_conditional:
                graph.add_edge(last_node, END)

        # --- Determine interrupt_before nodes ---
        interrupt_before: list[str] | None = None
        if definition.interrupt_before:
            interrupt_before = list(definition.interrupt_before)
        else:
            # Auto-detect approval gates
            approval_nodes = [n for n in definition.graph_nodes if "approval_gate" in n]
            if approval_nodes:
                interrupt_before = approval_nodes

        return graph.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_before or None,
        )
