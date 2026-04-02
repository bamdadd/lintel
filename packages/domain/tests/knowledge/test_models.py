"""Tests for knowledge domain models."""

from lintel.domain.knowledge.models import EdgeRelationship, ResearchEdge, ResearchNode


def test_research_node_is_frozen() -> None:
    node = ResearchNode(id="n1", topic="auth")
    try:
        node.id = "changed"  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass


def test_research_node_defaults() -> None:
    node = ResearchNode(id="n1", topic="auth")
    assert node.findings == ()
    assert node.confidence == 0.0
    assert node.source_run_id == ""
    assert node.created_at is not None


def test_research_edge_defaults() -> None:
    edge = ResearchEdge(parent_id="p", child_id="c")
    assert edge.relationship is EdgeRelationship.SUPPORTS


def test_edge_relationship_values() -> None:
    assert EdgeRelationship.EXTENDS == "extends"
    assert EdgeRelationship.CONTRADICTS == "contradicts"
    assert EdgeRelationship.SUPPORTS == "supports"
