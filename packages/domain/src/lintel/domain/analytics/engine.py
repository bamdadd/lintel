"""Analytics engine for team and contributor performance (REQ-F008)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lintel.domain.analytics.types import (
    ContributionRecord,
    ContributorStats,
    TeamStats,
    VelocityTrend,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class AnalyticsEngine:
    """Records contributions and computes analytics for contributors and teams.

    This is an in-memory engine suitable for domain-layer computation.
    Persistence is handled by the caller.
    """

    def __init__(self) -> None:
        self._records: list[ContributionRecord] = []
        self._teams: dict[str, _TeamInfo] = {}

    # -- recording ----------------------------------------------------------

    def record_contribution(
        self,
        user_id: str,
        event_type: str,
        metadata: dict[str, object] | None = None,
    ) -> ContributionRecord:
        """Append a contribution event."""
        record = ContributionRecord(
            user_id=user_id,
            event_type=event_type,
            metadata=metadata or {},
            timestamp=datetime.now(UTC),
        )
        self._records.append(record)
        return record

    def register_team(
        self,
        team_id: str,
        name: str,
        member_ids: Sequence[str],
    ) -> None:
        """Register or update a team for analytics queries."""
        self._teams[team_id] = _TeamInfo(team_id=team_id, name=name, member_ids=list(member_ids))

    # -- queries ------------------------------------------------------------

    def get_contributor_stats(
        self,
        user_id: str,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> ContributorStats:
        """Compute contributor stats, optionally filtered by time period."""
        records = self._filter(user_id=user_id, start=period_start, end=period_end)
        return _build_contributor_stats(user_id, records, period_start, period_end)

    def get_team_stats(
        self,
        team_id: str,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> TeamStats:
        """Compute team-level aggregate stats."""
        info = self._teams.get(team_id)
        if info is None:
            return TeamStats(team_id=team_id, name="unknown")

        records = [
            r
            for r in self._records
            if r.user_id in info.member_ids and _in_period(r.timestamp, period_start, period_end)
        ]

        commits = sum(1 for r in records if r.event_type == "commit")
        prs = sum(1 for r in records if r.event_type in {"pr_opened", "pr_merged"})
        cycle_times = [
            float(r.metadata.get("cycle_time_hours", 0))
            for r in records
            if "cycle_time_hours" in r.metadata
        ]
        avg_cycle = (sum(cycle_times) / len(cycle_times)) if cycle_times else 0.0

        return TeamStats(
            team_id=team_id,
            name=info.name,
            members=tuple(info.member_ids),
            total_commits=commits,
            total_prs=prs,
            avg_cycle_time_hours=avg_cycle,
            velocity_trend=self.calculate_velocity_trend(team_id),
        )

    def get_leaderboard(
        self,
        metric: str = "commits",
        limit: int = 10,
    ) -> list[ContributorStats]:
        """Return top contributors sorted by the given metric."""
        by_user: dict[str, list[ContributionRecord]] = defaultdict(list)
        for r in self._records:
            by_user[r.user_id].append(r)

        stats = [_build_contributor_stats(uid, recs, None, None) for uid, recs in by_user.items()]

        key_fn = {
            "commits": lambda s: s.commits,
            "prs_opened": lambda s: s.prs_opened,
            "prs_merged": lambda s: s.prs_merged,
            "reviews_given": lambda s: s.reviews_given,
            "lines_added": lambda s: s.lines_added,
        }.get(metric, lambda s: s.commits)

        stats.sort(key=key_fn, reverse=True)
        return stats[:limit]

    def calculate_velocity_trend(self, team_id: str) -> VelocityTrend:
        """Determine whether team velocity is accelerating, stable, or decelerating.

        Uses a simple heuristic: compare commit counts in the first and second
        halves of the recorded history for the team.
        """
        info = self._teams.get(team_id)
        if info is None:
            return VelocityTrend.STABLE

        records = sorted(
            (r for r in self._records if r.user_id in info.member_ids and r.event_type == "commit"),
            key=lambda r: r.timestamp or datetime.min,
        )
        if len(records) < 2:
            return VelocityTrend.STABLE

        mid = len(records) // 2
        first_half = len(records[:mid])
        second_half = len(records[mid:])

        if second_half > first_half:
            return VelocityTrend.ACCELERATING
        if second_half < first_half:
            return VelocityTrend.DECELERATING
        return VelocityTrend.STABLE

    # -- internals ----------------------------------------------------------

    def _filter(
        self,
        user_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[ContributionRecord]:
        return [
            r
            for r in self._records
            if (user_id is None or r.user_id == user_id) and _in_period(r.timestamp, start, end)
        ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


class _TeamInfo:
    __slots__ = ("member_ids", "name", "team_id")

    def __init__(self, team_id: str, name: str, member_ids: list[str]) -> None:
        self.team_id = team_id
        self.name = name
        self.member_ids = member_ids


def _in_period(
    ts: datetime | None,
    start: datetime | None,
    end: datetime | None,
) -> bool:
    if ts is None:
        return True
    if start and ts < start:
        return False
    return not (end and ts > end)


def _build_contributor_stats(
    user_id: str,
    records: list[ContributionRecord],
    period_start: datetime | None,
    period_end: datetime | None,
) -> ContributorStats:
    commits = sum(1 for r in records if r.event_type == "commit")
    prs_opened = sum(1 for r in records if r.event_type == "pr_opened")
    prs_merged = sum(1 for r in records if r.event_type == "pr_merged")
    reviews = sum(1 for r in records if r.event_type == "review")
    review_times = [
        float(r.metadata.get("review_time_hours", 0))
        for r in records
        if r.event_type == "review" and "review_time_hours" in r.metadata
    ]
    avg_review = (sum(review_times) / len(review_times)) if review_times else 0.0
    lines_added = sum(int(r.metadata.get("lines_added", 0)) for r in records)
    lines_removed = sum(int(r.metadata.get("lines_removed", 0)) for r in records)

    name = ""
    for r in records:
        if "name" in r.metadata:
            name = str(r.metadata["name"])
            break

    return ContributorStats(
        user_id=user_id,
        name=name,
        commits=commits,
        prs_opened=prs_opened,
        prs_merged=prs_merged,
        reviews_given=reviews,
        avg_review_time_hours=avg_review,
        lines_added=lines_added,
        lines_removed=lines_removed,
        period_start=period_start,
        period_end=period_end,
    )
