"""LangGraph state graph definition for the review-and-improve workflow."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from lintel.workflows.review_and_improve.nodes.aggregate_scores import aggregate_scores
from lintel.workflows.review_and_improve.nodes.analyze_dimension import (
    analyze_architecture,
    analyze_correctness,
    analyze_maintainability,
    analyze_performance,
    analyze_security,
)
from lintel.workflows.review_and_improve.nodes.fetch_commits import fetch_commits
from lintel.workflows.review_and_improve.nodes.generate_fix_pr import generate_fix_pr
from lintel.workflows.review_and_improve.nodes.generate_report import generate_report
from lintel.workflows.review_and_improve.state import ReviewWorkflowState


def _should_generate_fix_pr(state: dict[str, Any]) -> str:
    """Route after report generation: generate fix PR or end."""
    if not state.get("improvement_mode", False):
        return "end"
    threshold = state.get("severity_threshold", "high")
    aggregated = state.get("aggregated_scores", {})
    severity_order = ["info", "low", "medium", "high", "critical"]
    threshold_idx = severity_order.index(threshold) if threshold in severity_order else 3
    # Check if any dimension has findings at or above the threshold
    for _dim, score in aggregated.items():
        if score >= threshold_idx:
            return "generate_fix_pr"
    return "end"


def build_review_and_improve_graph() -> StateGraph:
    """Build the review-and-improve workflow graph."""
    graph = StateGraph(ReviewWorkflowState)

    # Add nodes
    graph.add_node("fetch_commits", fetch_commits)
    graph.add_node("analyze_correctness", analyze_correctness)
    graph.add_node("analyze_security", analyze_security)
    graph.add_node("analyze_performance", analyze_performance)
    graph.add_node("analyze_maintainability", analyze_maintainability)
    graph.add_node("analyze_architecture", analyze_architecture)
    graph.add_node("aggregate_scores", aggregate_scores)
    graph.add_node("generate_report", generate_report)
    graph.add_node("generate_fix_pr", generate_fix_pr)

    # Wire edges (sequential for now; analysis nodes run in sequence)
    graph.set_entry_point("fetch_commits")
    graph.add_edge("fetch_commits", "analyze_correctness")
    graph.add_edge("analyze_correctness", "analyze_security")
    graph.add_edge("analyze_security", "analyze_performance")
    graph.add_edge("analyze_performance", "analyze_maintainability")
    graph.add_edge("analyze_maintainability", "analyze_architecture")
    graph.add_edge("analyze_architecture", "aggregate_scores")
    graph.add_edge("aggregate_scores", "generate_report")

    # Conditional edge: generate fix PR or end
    graph.add_conditional_edges(
        "generate_report",
        _should_generate_fix_pr,
        {"generate_fix_pr": "generate_fix_pr", "end": END},
    )
    graph.add_edge("generate_fix_pr", END)

    return graph
