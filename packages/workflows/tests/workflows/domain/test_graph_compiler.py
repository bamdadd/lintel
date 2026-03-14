"""Tests for GraphCompiler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lintel.workflows.graph_compiler import GraphCompiler


def _sample_graph_def() -> dict[str, list[dict[str, str]]]:
    return {
        "nodes": [
            {"id": "planner", "type": "agentStep", "role": "planner"},
            {"id": "coder", "type": "agentStep", "role": "coder"},
            {"id": "review_gate", "type": "approvalGate", "role": ""},
        ],
        "edges": [
            {"source": "__start__", "target": "planner"},
            {"source": "planner", "target": "coder"},
            {"source": "coder", "target": "review_gate"},
        ],
    }


async def _dummy_node(state: dict) -> dict:
    return state


def test_compile_creates_graph_with_expected_nodes() -> None:
    registry: dict[str, object] = {
        "agentStep:planner": _dummy_node,
        "agentStep:coder": _dummy_node,
        "approvalGate:": _dummy_node,
    }
    compiler = GraphCompiler(node_registry=registry)
    definition = MagicMock()
    definition.graph = _sample_graph_def()

    compiled = compiler.compile(definition, checkpointer=None)

    # Verify nodes are present (LangGraph nodes dict includes __start__ and __end__)
    node_names = set(compiled.nodes.keys())
    assert "planner" in node_names
    assert "coder" in node_names
    assert "review_gate" in node_names


def test_compile_raises_for_unknown_node_type() -> None:
    compiler = GraphCompiler(node_registry={})
    definition = MagicMock()
    definition.graph = {
        "nodes": [{"id": "unknown", "type": "nonexistent", "role": "x"}],
        "edges": [{"source": "__start__", "target": "unknown"}],
    }

    with pytest.raises(ValueError, match="No handler registered"):
        compiler.compile(definition, checkpointer=None)
