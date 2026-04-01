"""Review score metrics for observability (REQ-006)."""

from __future__ import annotations

from opentelemetry.metrics import get_meter

meter = get_meter("lintel.review")

review_score_gauge = meter.create_gauge(
    name="lintel_review_score",
    description="Current review score per repo and dimension",
    unit="score",
)

review_score_trend_counter = meter.create_counter(
    name="lintel_review_score_trend_total",
    description="Count of improvement or regression events per repo",
    unit="events",
)

fix_pr_triggered_counter = meter.create_counter(
    name="lintel_fix_pr_triggered_total",
    description="Count of fix PRs triggered per repo",
    unit="events",
)


def emit_review_score(
    repo_id: str,
    dimension: str,
    score: float,
) -> None:
    """Emit a review score gauge metric."""
    review_score_gauge.set(
        score,
        attributes={
            "repo_id": repo_id,
            "dimension": dimension,
        },
    )


def emit_score_trend(
    repo_id: str,
    dimension: str,
    direction: str,
) -> None:
    """Emit a score trend event (improvement or regression)."""
    review_score_trend_counter.add(
        1,
        attributes={
            "repo_id": repo_id,
            "dimension": dimension,
            "direction": direction,
        },
    )


def emit_fix_pr_triggered(repo_id: str) -> None:
    """Emit a fix PR triggered counter increment."""
    fix_pr_triggered_counter.add(
        1,
        attributes={
            "repo_id": repo_id,
        },
    )
