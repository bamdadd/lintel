"""State definition for the review-and-improve workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class ReviewWorkflowState(TypedDict, total=False):
    """Shared state for the review-and-improve workflow graph."""

    # Input
    repo_id: str
    contributor_id: str
    improvement_mode: bool
    severity_threshold: str
    lookback_days: int

    # Intermediate
    commit_shas: list[str]
    diff_content: str
    per_dimension_results: dict[str, Any]
    aggregated_scores: dict[str, float]

    # Output
    report_id: str
    fix_pr_triggered: bool
    error: str
