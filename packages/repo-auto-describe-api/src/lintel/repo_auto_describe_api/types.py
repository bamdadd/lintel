"""Repository auto-describe domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class DescribeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class RepoDescription:
    """Result of auto-describing a repository."""

    id: str
    repo_id: str
    summary: str = ""
    languages: tuple[str, ...] = ()
    frameworks: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    status: DescribeStatus = DescribeStatus.PENDING
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = ""
