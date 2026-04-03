"""Digest domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Digest:
    """A generated team progress digest for a time period."""

    id: str
    project_id: str
    team_id: str
    period_start: datetime
    period_end: datetime
    summary: str
    metrics: dict[str, object] = field(default_factory=dict)
    highlights: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DigestConfig:
    """Configuration for automated digest generation."""

    id: str
    project_id: str
    schedule: str = "weekly"
    recipients: tuple[str, ...] = ()
    enabled: bool = True
