"""Team and contributor analytics domain types (REQ-F008)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class VelocityTrend(StrEnum):
    """Direction of team velocity over the measured period."""

    ACCELERATING = "accelerating"
    STABLE = "stable"
    DECELERATING = "decelerating"


@dataclass(frozen=True)
class ContributorStats:
    """Aggregated statistics for a single contributor over a time period."""

    user_id: str
    name: str
    commits: int = 0
    prs_opened: int = 0
    prs_merged: int = 0
    reviews_given: int = 0
    avg_review_time_hours: float = 0.0
    lines_added: int = 0
    lines_removed: int = 0
    period_start: datetime | None = None
    period_end: datetime | None = None


@dataclass(frozen=True)
class TeamStats:
    """Aggregated statistics for a team over a time period."""

    team_id: str
    name: str
    members: tuple[str, ...] = ()
    total_commits: int = 0
    total_prs: int = 0
    avg_cycle_time_hours: float = 0.0
    velocity_trend: VelocityTrend = VelocityTrend.STABLE


@dataclass(frozen=True)
class ContributionRecord:
    """A single recorded contribution event."""

    user_id: str
    event_type: str
    metadata: dict[str, object] = field(default_factory=dict)
    timestamp: datetime | None = None
