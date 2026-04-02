"""Tests for feedback domain types."""

from lintel.domain.feedback.types import ABVariant, FeedbackEntry, FeedbackType, LearningInsight


def test_feedback_type_values() -> None:
    assert FeedbackType.THUMBS_UP == "thumbs_up"
    assert FeedbackType.THUMBS_DOWN == "thumbs_down"
    assert FeedbackType.CORRECTION == "correction"
    assert FeedbackType.SUGGESTION == "suggestion"


def test_feedback_entry_defaults() -> None:
    entry = FeedbackEntry()
    assert entry.feedback_id
    assert entry.feedback_type == FeedbackType.THUMBS_UP
    assert entry.comment == ""


def test_feedback_entry_frozen() -> None:
    entry = FeedbackEntry(comment="good")
    try:
        entry.comment = "bad"  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass


def test_ab_variant_defaults() -> None:
    v = ABVariant(experiment_id="exp-1", name="control")
    assert v.variant_id
    assert v.config == {}
    assert v.metrics == {}


def test_learning_insight_defaults() -> None:
    insight = LearningInsight(pattern="repeated thumbs_down", frequency=5)
    assert insight.insight_id
    assert insight.confidence == 0.0
