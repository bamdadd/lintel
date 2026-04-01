"""Integration tests for the review-and-improve workflow lifecycle."""

from __future__ import annotations

from lintel.domain.review_events import FixPRTriggered, ReviewCompleted
from lintel.domain.review_types import ReviewDimension, ReviewSeverity


def test_review_events_are_registered() -> None:
    """Verify review events are in the global EVENT_TYPE_MAP."""
    from lintel.contracts.events import EVENT_TYPE_MAP

    # Force module import to trigger register_events
    import lintel.domain.review_events  # noqa: F401

    assert "ReviewCompleted" in EVENT_TYPE_MAP
    assert "ReviewScoreRecorded" in EVENT_TYPE_MAP
    assert "FixPRTriggered" in EVENT_TYPE_MAP


def test_review_dimension_enum() -> None:
    """Verify ReviewDimension has all 5 expected values."""
    assert len(ReviewDimension) == 5
    assert ReviewDimension.CORRECTNESS == "correctness"
    assert ReviewDimension.SECURITY == "security"
    assert ReviewDimension.PERFORMANCE == "performance"
    assert ReviewDimension.MAINTAINABILITY == "maintainability"
    assert ReviewDimension.ARCHITECTURE == "architecture"


def test_review_severity_enum() -> None:
    """Verify ReviewSeverity has all expected values."""
    assert ReviewSeverity.CRITICAL == "critical"
    assert ReviewSeverity.HIGH == "high"
    assert ReviewSeverity.MEDIUM == "medium"
    assert ReviewSeverity.LOW == "low"
    assert ReviewSeverity.INFO == "info"


def test_review_completed_event() -> None:
    """Verify ReviewCompleted event can be instantiated."""
    event = ReviewCompleted(
        payload={"report_id": "r1", "repo_id": "repo-1", "pipeline_run_id": "run-1"},
    )
    assert event.event_type == "ReviewCompleted"
    assert event.payload["report_id"] == "r1"


def test_fix_pr_triggered_event() -> None:
    """Verify FixPRTriggered event can be instantiated."""
    event = FixPRTriggered(
        payload={"repo_id": "repo-1", "report_id": "r1"},
    )
    assert event.event_type == "FixPRTriggered"
