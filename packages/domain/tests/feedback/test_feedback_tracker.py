"""Tests for FeedbackTracker."""

import pytest

from lintel.domain.feedback.tracker import FeedbackTracker
from lintel.domain.feedback.types import ABVariant, FeedbackEntry, FeedbackType


@pytest.fixture()
def tracker() -> FeedbackTracker:
    return FeedbackTracker()


class TestRecordAndQuery:
    def test_record_and_get_all(self, tracker: FeedbackTracker) -> None:
        entry = FeedbackEntry(agent_id="coder", feedback_type=FeedbackType.THUMBS_UP)
        tracker.record_feedback(entry)
        assert tracker.get_feedback() == [entry]

    def test_filter_by_agent(self, tracker: FeedbackTracker) -> None:
        tracker.record_feedback(FeedbackEntry(agent_id="coder"))
        tracker.record_feedback(FeedbackEntry(agent_id="reviewer"))
        assert len(tracker.get_feedback(agent_id="coder")) == 1

    def test_filter_by_type(self, tracker: FeedbackTracker) -> None:
        tracker.record_feedback(FeedbackEntry(agent_id="a", feedback_type=FeedbackType.THUMBS_UP))
        tracker.record_feedback(FeedbackEntry(agent_id="a", feedback_type=FeedbackType.THUMBS_DOWN))
        results = tracker.get_feedback(feedback_type=FeedbackType.THUMBS_DOWN)
        assert len(results) == 1

    def test_filter_by_workflow_run(self, tracker: FeedbackTracker) -> None:
        tracker.record_feedback(FeedbackEntry(workflow_run_id="run-1"))
        tracker.record_feedback(FeedbackEntry(workflow_run_id="run-2"))
        assert len(tracker.get_feedback(workflow_run_id="run-1")) == 1

    def test_filter_by_stage(self, tracker: FeedbackTracker) -> None:
        tracker.record_feedback(FeedbackEntry(stage_id="implement"))
        tracker.record_feedback(FeedbackEntry(stage_id="review"))
        assert len(tracker.get_feedback(stage_id="review")) == 1


class TestSatisfactionRate:
    def test_no_feedback_returns_zero(self, tracker: FeedbackTracker) -> None:
        assert tracker.compute_satisfaction_rate("coder") == 0.0

    def test_all_positive(self, tracker: FeedbackTracker) -> None:
        for _ in range(3):
            tracker.record_feedback(
                FeedbackEntry(agent_id="coder", feedback_type=FeedbackType.THUMBS_UP)
            )
        assert tracker.compute_satisfaction_rate("coder") == 1.0

    def test_mixed_feedback(self, tracker: FeedbackTracker) -> None:
        tracker.record_feedback(
            FeedbackEntry(agent_id="coder", feedback_type=FeedbackType.THUMBS_UP)
        )
        tracker.record_feedback(
            FeedbackEntry(agent_id="coder", feedback_type=FeedbackType.THUMBS_DOWN)
        )
        assert tracker.compute_satisfaction_rate("coder") == 0.5


class TestInsights:
    def test_no_insights_below_threshold(self, tracker: FeedbackTracker) -> None:
        tracker.record_feedback(FeedbackEntry(agent_id="a", feedback_type=FeedbackType.THUMBS_UP))
        assert tracker.extract_insights(min_frequency=2) == []

    def test_extracts_recurring_pattern(self, tracker: FeedbackTracker) -> None:
        for _ in range(3):
            tracker.record_feedback(
                FeedbackEntry(agent_id="coder", feedback_type=FeedbackType.THUMBS_DOWN)
            )
        insights = tracker.extract_insights(min_frequency=2)
        assert len(insights) == 1
        assert "coder" in insights[0].pattern
        assert insights[0].frequency == 3


class TestABComparison:
    def test_compare_returns_winner(self, tracker: FeedbackTracker) -> None:
        v1 = ABVariant(
            variant_id="v1",
            experiment_id="exp-1",
            name="control",
            metrics={"satisfaction": 0.6},
        )
        v2 = ABVariant(
            variant_id="v2",
            experiment_id="exp-1",
            name="treatment",
            metrics={"satisfaction": 0.8},
        )
        tracker.register_variant(v1)
        tracker.register_variant(v2)
        winner = tracker.compare_variants("exp-1")
        assert winner.variant_id == "v2"

    def test_compare_no_variants_raises(self, tracker: FeedbackTracker) -> None:
        with pytest.raises(ValueError, match="No variants"):
            tracker.compare_variants("nonexistent")

    def test_record_variant_metrics(self, tracker: FeedbackTracker) -> None:
        v = ABVariant(variant_id="v1", experiment_id="exp-1", name="control")
        tracker.register_variant(v)
        tracker.record_variant_metrics("exp-1", "v1", {"satisfaction": 0.9})
        winner = tracker.compare_variants("exp-1")
        assert winner.metrics["satisfaction"] == 0.9
