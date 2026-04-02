"""Feedback loop and A/B experiment domain types (REQ-F021)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class FeedbackType(StrEnum):
    """Kind of feedback submitted by a user."""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CORRECTION = "correction"
    SUGGESTION = "suggestion"


@dataclass(frozen=True)
class FeedbackEntry:
    """A single piece of feedback on a workflow stage or agent output."""

    feedback_id: str = field(default_factory=lambda: str(uuid4()))
    workflow_run_id: str = ""
    stage_id: str = ""
    agent_id: str = ""
    feedback_type: FeedbackType = FeedbackType.THUMBS_UP
    comment: str = ""
    submitted_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ABVariant:
    """One variant in an A/B experiment, with its accumulated metrics."""

    variant_id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    name: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningInsight:
    """A pattern extracted from accumulated feedback data."""

    insight_id: str = field(default_factory=lambda: str(uuid4()))
    pattern: str = ""
    frequency: int = 0
    recommendation: str = ""
    confidence: float = 0.0
