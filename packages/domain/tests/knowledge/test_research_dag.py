"""Tests for ResearchDAG."""

import pytest

from lintel.domain.knowledge.models import EdgeRelationship, ResearchEdge, ResearchNode
from lintel.domain.knowledge.research_dag import CycleError, ResearchDAG


def _node(nid: str, topic: str = "default", findings: tuple[str, ...] = ()) -> ResearchNode:
    return ResearchNode(id=nid, topic=topic, findings=findings)


def test_add_and_retrieve_node() -> None:
    dag = ResearchDAG()
    n = _node("a")
    dag.add_node(n)
    assert dag.get_node("a") is n


def test_add_duplicate_node_raises() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("a"))
    with pytest.raises(ValueError, match="already exists"):
        dag.add_node(_node("a"))


def test_add_edge_missing_parent() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("c"))
    with pytest.raises(KeyError, match="Parent"):
        dag.add_edge(ResearchEdge(parent_id="missing", child_id="c"))


def test_add_edge_missing_child() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("p"))
    with pytest.raises(KeyError, match="Child"):
        dag.add_edge(ResearchEdge(parent_id="p", child_id="missing"))


def test_self_loop_raises() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("a"))
    with pytest.raises(CycleError, match="Self-loop"):
        dag.add_edge(ResearchEdge(parent_id="a", child_id="a"))


def test_cycle_detection() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("a"))
    dag.add_node(_node("b"))
    dag.add_node(_node("c"))
    dag.add_edge(ResearchEdge(parent_id="a", child_id="b"))
    dag.add_edge(ResearchEdge(parent_id="b", child_id="c"))
    with pytest.raises(CycleError, match="cycle"):
        dag.add_edge(ResearchEdge(parent_id="c", child_id="a"))


def test_get_ancestors() -> None:
    dag = ResearchDAG()
    for nid in ("a", "b", "c"):
        dag.add_node(_node(nid))
    dag.add_edge(ResearchEdge(parent_id="a", child_id="b"))
    dag.add_edge(ResearchEdge(parent_id="b", child_id="c"))
    assert dag.get_ancestors("c") == {"a", "b"}
    assert dag.get_ancestors("a") == set()


def test_get_descendants() -> None:
    dag = ResearchDAG()
    for nid in ("a", "b", "c"):
        dag.add_node(_node(nid))
    dag.add_edge(ResearchEdge(parent_id="a", child_id="b"))
    dag.add_edge(ResearchEdge(parent_id="a", child_id="c"))
    assert dag.get_descendants("a") == {"b", "c"}
    assert dag.get_descendants("c") == set()


def test_find_relevant_case_insensitive() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("a", topic="Authentication flow"))
    dag.add_node(_node("b", topic="Database schema"))
    results = dag.find_relevant("auth")
    assert len(results) == 1
    assert results[0].id == "a"


def test_find_relevant_no_match() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("a", topic="auth"))
    assert dag.find_relevant("xyz") == []


def test_merge_findings_deduplicates() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("a", findings=("f1", "f2")))
    dag.add_node(_node("b", findings=("f2", "f3")))
    merged = dag.merge_findings(["a", "b"])
    assert merged == ["f1", "f2", "f3"]


def test_merge_findings_preserves_order() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("x", findings=("c", "a")))
    dag.add_node(_node("y", findings=("b",)))
    assert dag.merge_findings(["x", "y"]) == ["c", "a", "b"]


def test_nodes_and_edges_properties() -> None:
    dag = ResearchDAG()
    dag.add_node(_node("a"))
    dag.add_node(_node("b"))
    edge = ResearchEdge(parent_id="a", child_id="b", relationship=EdgeRelationship.EXTENDS)
    dag.add_edge(edge)
    assert len(dag.nodes) == 2
    assert len(dag.edges) == 1
    assert dag.edges[0].relationship is EdgeRelationship.EXTENDS
