"""Tests for review metrics emission."""

from __future__ import annotations

from lintel.observability.review_metrics import (
    emit_fix_pr_triggered,
    emit_review_score,
    emit_score_trend,
)


def test_emit_review_score() -> None:
    """Verify emit_review_score does not raise."""
    emit_review_score(repo_id="repo-1", dimension="security", score=7.5)


def test_emit_score_trend() -> None:
    """Verify emit_score_trend does not raise."""
    emit_score_trend(repo_id="repo-1", dimension="security", direction="improvement")


def test_emit_fix_pr_triggered() -> None:
    """Verify emit_fix_pr_triggered does not raise."""
    emit_fix_pr_triggered(repo_id="repo-1")
