"""Review comment types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class ReviewSeverity(Enum):
    """Severity level for a review comment."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReviewCommentStatus(Enum):
    """Status of a review comment."""

    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass(frozen=True)
class ReviewComment:
    """A code review comment attached to a pipeline run."""

    id: str = field(default_factory=lambda: str(uuid4()))
    pipeline_run_id: str = ""
    file_path: str = ""
    line_number: int = 0
    comment: str = ""
    severity: ReviewSeverity = ReviewSeverity.INFO
    suggestion: str = ""
    status: ReviewCommentStatus = ReviewCommentStatus.OPEN
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
