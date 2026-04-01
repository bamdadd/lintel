"""Tests for pipeline_graph domain models."""

from __future__ import annotations

from lintel.domain.pipeline_graph.models import (
    EdgeType,
    NodePosition,
    NodeType,
    PipelineEdge,
    PipelineGraph,
    PipelineNode,
)


def _make_node(node_id: str, *, node_type: NodeType = NodeType.STAGE) -> PipelineNode:
    return PipelineNode(node_id=node_id, name=node_id, node_type=node_type)


def _make_edge(src: str, tgt: str, *, edge_type: EdgeType = EdgeType.EXECUTION) -> PipelineEdge:
    return PipelineEdge(source_id=src, target_id=tgt, edge_type=edge_type)


# ------------------------------------------------------------------
# PipelineNode
# ------------------------------------------------------------------


def test_node_frozen() -> None:
    node = _make_node("a")
    try:
        node.name = "changed"  # type: ignore[misc]
        raised = False
    except AttributeError:
        raised = True
    assert raised


def test_node_default_position() -> None:
    node = _make_node("a")
    assert node.position == NodePosition()


def test_node_custom_metadata() -> None:
    node = PipelineNode(node_id="x", name="x", node_type=NodeType.ARTIFACT, metadata={"key": "val"})
    assert node.metadata["key"] == "val"


# ------------------------------------------------------------------
# PipelineEdge
# ------------------------------------------------------------------


def test_edge_frozen() -> None:
    edge = _make_edge("a", "b")
    try:
        edge.label = "changed"  # type: ignore[misc]
        raised = False
    except AttributeError:
        raised = True
    assert raised


def test_edge_default_label() -> None:
    edge = _make_edge("a", "b")
    assert edge.label == ""


# ------------------------------------------------------------------
# PipelineGraph query helpers
# ------------------------------------------------------------------


def _sample_graph() -> PipelineGraph:
    nodes = (
        _make_node("t1", node_type=NodeType.TRIGGER),
        _make_node("s1"),
        _make_node("s2"),
        _make_node("a1", node_type=NodeType.ARTIFACT),
    )
    edges = (
        _make_edge("t1", "s1", edge_type=EdgeType.TRIGGER),
        _make_edge("s1", "s2"),
        _make_edge("s2", "a1", edge_type=EdgeType.DATA_FLOW),
    )
    return PipelineGraph(nodes=nodes, edges=edges)


def test_node_by_id_found() -> None:
    g = _sample_graph()
    assert g.node_by_id("s1") is not None
    assert g.node_by_id("s1").node_id == "s1"  # type: ignore[union-attr]


def test_node_by_id_not_found() -> None:
    g = _sample_graph()
    assert g.node_by_id("missing") is None


def test_nodes_by_type() -> None:
    g = _sample_graph()
    stages = g.nodes_by_type(NodeType.STAGE)
    assert len(stages) == 2


def test_edges_from() -> None:
    g = _sample_graph()
    assert len(g.edges_from("s1")) == 1
    assert g.edges_from("s1")[0].target_id == "s2"


def test_edges_to() -> None:
    g = _sample_graph()
    assert len(g.edges_to("s2")) == 1
    assert g.edges_to("s2")[0].source_id == "s1"


def test_successors() -> None:
    g = _sample_graph()
    assert g.successors("s1") == ("s2",)


def test_predecessors() -> None:
    g = _sample_graph()
    assert g.predecessors("s2") == ("s1",)


def test_empty_graph() -> None:
    g = PipelineGraph()
    assert g.nodes == ()
    assert g.edges == ()
    assert g.node_by_id("x") is None


def test_enum_values() -> None:
    assert NodeType.TRIGGER == "trigger"
    assert EdgeType.DATA_FLOW == "data_flow"
