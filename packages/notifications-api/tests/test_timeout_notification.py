"""Unit test: Stage timeout notification dispatch."""

from __future__ import annotations

from lintel.workflows.nodes._stage_tracking import _pattern_matches


def test_pattern_matches_timed_out() -> None:
    """Notification pattern matching works with timed_out status."""
    assert _pattern_matches("*.timed_out", "implement.timed_out")
    assert _pattern_matches("implement.timed_out", "implement.timed_out")
    assert _pattern_matches("*", "implement.timed_out")
    assert not _pattern_matches("implement.failed", "implement.timed_out")


def test_pattern_matches_wildcard_stage() -> None:
    """Wildcard stage matching with timed_out status."""
    assert _pattern_matches("*.timed_out", "research.timed_out")
    assert _pattern_matches("*.timed_out", "plan.timed_out")
