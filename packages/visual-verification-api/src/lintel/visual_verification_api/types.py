"""Visual verification domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class VerificationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class VisualVerification:
    """A before/after screenshot verification for a pipeline stage."""

    id: str
    pipeline_run_id: str
    stage_name: str
    before_url: str = ""
    after_url: str = ""
    diff_url: str = ""
    status: VerificationStatus = VerificationStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
