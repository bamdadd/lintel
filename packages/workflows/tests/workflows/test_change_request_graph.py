"""Tests for the change_request workflow graph."""

from __future__ import annotations

from lintel.workflows.change_request import (
    _change_request_review_decision,
    build_change_request_graph,
)


def test_build_change_request_graph_structure() -> None:
    """Graph should have setup_workspace, implement, review, close nodes."""
    graph = build_change_request_graph()
    node_names = set(graph.nodes)
    assert "setup_workspace" in node_names
    assert "implement" in node_names
    assert "review" in node_names
    assert "close" in node_names
    # Should NOT have research or plan nodes
    assert "research" not in node_names
    assert "plan" not in node_names
    assert "ingest" not in node_names
    assert "route" not in node_names


def test_review_decision_approve_goes_to_close() -> None:
    state = {
        "error": None,
        "review_cycles": 0,
        "agent_outputs": [{"node": "review", "verdict": "approve"}],
    }
    assert _change_request_review_decision(state) == "close"


def test_review_decision_request_changes_goes_to_revise() -> None:
    state = {
        "error": None,
        "review_cycles": 0,
        "agent_outputs": [{"node": "review", "verdict": "request_changes"}],
    }
    assert _change_request_review_decision(state) == "revise"


def test_review_decision_max_cycles_goes_to_close() -> None:
    state = {
        "error": None,
        "review_cycles": 5,
        "agent_outputs": [{"node": "review", "verdict": "request_changes"}],
    }
    assert _change_request_review_decision(state) == "close"


def test_review_decision_error_goes_to_close() -> None:
    state = {
        "error": "something broke",
        "review_cycles": 0,
        "agent_outputs": [],
    }
    assert _change_request_review_decision(state) == "close"


def test_review_decision_no_review_output_goes_to_close() -> None:
    state = {
        "error": None,
        "review_cycles": 0,
        "agent_outputs": [],
    }
    assert _change_request_review_decision(state) == "close"
