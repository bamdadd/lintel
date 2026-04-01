"""Review-and-improve workflow events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events

# --- Review Events ---


@dataclass(frozen=True)
class ReviewCompleted(EventEnvelope):
    """A review-and-improve workflow completed and produced a report."""

    event_type: str = "ReviewCompleted"


@dataclass(frozen=True)
class ReviewScoreRecorded(EventEnvelope):
    """A review dimension score was recorded for trend tracking."""

    event_type: str = "ReviewScoreRecorded"


@dataclass(frozen=True)
class FixPRTriggered(EventEnvelope):
    """Improvement mode triggered a fix PR for high-severity findings."""

    event_type: str = "FixPRTriggered"


register_events(
    ReviewCompleted,
    ReviewScoreRecorded,
    FixPRTriggered,
)
