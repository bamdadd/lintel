"""Tests for the review-and-improve workflow graph."""

from __future__ import annotations

from lintel.workflows.review_and_improve.graph import (
    _should_generate_fix_pr,
    build_review_and_improve_graph,
)


def test_build_graph() -> None:
    """Verify the graph can be built without error."""
    graph = build_review_and_improve_graph()
    assert graph is not None


def test_should_generate_fix_pr_disabled() -> None:
    """When improvement_mode is off, should return 'end'."""
    state = {"improvement_mode": False, "aggregated_scores": {"security": 9.0}}
    assert _should_generate_fix_pr(state) == "end"


def test_should_generate_fix_pr_below_threshold() -> None:
    """When scores are below threshold, should return 'end'."""
    state = {
        "improvement_mode": True,
        "severity_threshold": "high",
        "aggregated_scores": {"security": 1.0, "correctness": 2.0},
    }
    assert _should_generate_fix_pr(state) == "end"


def test_should_generate_fix_pr_above_threshold() -> None:
    """When scores are at or above threshold, should return 'generate_fix_pr'."""
    state = {
        "improvement_mode": True,
        "severity_threshold": "high",
        "aggregated_scores": {"security": 5.0},
    }
    assert _should_generate_fix_pr(state) == "generate_fix_pr"


def test_should_generate_fix_pr_default_threshold() -> None:
    """Default threshold is 'high' (index 3)."""
    state = {
        "improvement_mode": True,
        "aggregated_scores": {"correctness": 3.0},
    }
    assert _should_generate_fix_pr(state) == "generate_fix_pr"
