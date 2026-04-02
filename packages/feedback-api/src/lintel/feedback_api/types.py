"""Feedback ingestion domain types (REQ-025)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class FeedbackCategory(StrEnum):
    """AI-assigned category for user/product feedback."""

    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    PERFORMANCE = "performance"
    UX = "ux"
    OTHER = "other"


class FeedbackStatus(StrEnum):
    """Lifecycle status of a feedback entry."""

    NEW = "new"
    CATEGORIZED = "categorized"
    TRIAGED = "triaged"
    WORK_ITEM_CREATED = "work_item_created"
    CLOSED = "closed"


class FeedbackPriority(StrEnum):
    """Priority level assigned to feedback."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class FeedbackTechnicalContext:
    """Optional technical context attached to feedback."""

    browser: str = ""
    device: str = ""
    os: str = ""
    session_id: str = ""
    url: str = ""
    recent_changes: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductFeedback:
    """A single piece of user/product feedback (REQ-025).

    Distinct from ``lintel.domain.feedback.types.FeedbackEntry`` which tracks
    workflow/agent feedback (REQ-F021).
    """

    feedback_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    submitted_by: str = ""
    title: str = ""
    body: str = ""
    category: FeedbackCategory = FeedbackCategory.OTHER
    status: FeedbackStatus = FeedbackStatus.NEW
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    tags: tuple[str, ...] = ()
    technical_context: FeedbackTechnicalContext = field(
        default_factory=FeedbackTechnicalContext,
    )
    work_item_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
