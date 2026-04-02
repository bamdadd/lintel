"""Tests for AnalyticsEngine."""

from lintel.domain.analytics.engine import AnalyticsEngine
from lintel.domain.analytics.types import VelocityTrend


def test_record_and_get_contributor_stats() -> None:
    engine = AnalyticsEngine()
    engine.record_contribution("u1", "commit", {"name": "Alice", "lines_added": 50})
    engine.record_contribution("u1", "commit", {"lines_added": 30})
    engine.record_contribution("u1", "pr_opened")
    engine.record_contribution("u1", "pr_merged")
    engine.record_contribution("u1", "review", {"review_time_hours": 2.0})

    stats = engine.get_contributor_stats("u1")
    assert stats.commits == 2
    assert stats.prs_opened == 1
    assert stats.prs_merged == 1
    assert stats.reviews_given == 1
    assert stats.avg_review_time_hours == 2.0
    assert stats.lines_added == 80
    assert stats.name == "Alice"


def test_get_contributor_stats_empty() -> None:
    engine = AnalyticsEngine()
    stats = engine.get_contributor_stats("nobody")
    assert stats.commits == 0
    assert stats.name == ""


def test_team_stats() -> None:
    engine = AnalyticsEngine()
    engine.register_team("t1", "Backend", ["u1", "u2"])
    engine.record_contribution("u1", "commit")
    engine.record_contribution("u2", "commit")
    engine.record_contribution("u2", "pr_opened")
    engine.record_contribution("u3", "commit")  # not in team

    ts = engine.get_team_stats("t1")
    assert ts.total_commits == 2
    assert ts.total_prs == 1
    assert ts.name == "Backend"
    assert set(ts.members) == {"u1", "u2"}


def test_team_stats_unknown_team() -> None:
    engine = AnalyticsEngine()
    ts = engine.get_team_stats("nonexistent")
    assert ts.name == "unknown"
    assert ts.total_commits == 0


def test_leaderboard() -> None:
    engine = AnalyticsEngine()
    for _ in range(5):
        engine.record_contribution("u1", "commit")
    for _ in range(3):
        engine.record_contribution("u2", "commit")
    engine.record_contribution("u3", "commit")

    board = engine.get_leaderboard("commits", limit=2)
    assert len(board) == 2
    assert board[0].user_id == "u1"
    assert board[0].commits == 5
    assert board[1].user_id == "u2"


def test_velocity_trend_accelerating() -> None:
    engine = AnalyticsEngine()
    engine.register_team("t1", "Team", ["u1"])
    # First half: 1 commit, second half: 3 commits
    engine.record_contribution("u1", "commit")
    engine.record_contribution("u1", "commit")
    engine.record_contribution("u1", "commit")
    engine.record_contribution("u1", "commit")
    # With 4 records split in half: 2 vs 2 = stable
    # Need odd split for acceleration
    engine.record_contribution("u1", "commit")
    # 5 records: first 2 vs last 3 → accelerating
    assert engine.calculate_velocity_trend("t1") == VelocityTrend.ACCELERATING


def test_velocity_trend_stable_no_data() -> None:
    engine = AnalyticsEngine()
    assert engine.calculate_velocity_trend("t1") == VelocityTrend.STABLE


def test_leaderboard_by_reviews() -> None:
    engine = AnalyticsEngine()
    engine.record_contribution("u1", "review")
    engine.record_contribution("u2", "review")
    engine.record_contribution("u2", "review")

    board = engine.get_leaderboard("reviews_given", limit=10)
    assert board[0].user_id == "u2"
    assert board[0].reviews_given == 2
