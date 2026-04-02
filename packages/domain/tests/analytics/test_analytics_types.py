"""Tests for analytics domain types."""

from lintel.domain.analytics.types import (
    ContributionRecord,
    ContributorStats,
    TeamStats,
    VelocityTrend,
)


def test_velocity_trend_values() -> None:
    assert VelocityTrend.ACCELERATING == "accelerating"
    assert VelocityTrend.STABLE == "stable"
    assert VelocityTrend.DECELERATING == "decelerating"


def test_contributor_stats_frozen() -> None:
    stats = ContributorStats(user_id="u1", name="Alice", commits=5)
    assert stats.user_id == "u1"
    assert stats.commits == 5
    assert stats.prs_opened == 0


def test_team_stats_defaults() -> None:
    ts = TeamStats(team_id="t1", name="Backend")
    assert ts.members == ()
    assert ts.total_commits == 0
    assert ts.velocity_trend == VelocityTrend.STABLE


def test_contribution_record_defaults() -> None:
    rec = ContributionRecord(user_id="u1", event_type="commit")
    assert rec.metadata == {}
    assert rec.timestamp is None
