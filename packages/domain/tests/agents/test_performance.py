"""Tests for agent performance tracking (REQ-F016)."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.agents.performance import (
    AgentGrade,
    GradeLevel,
    LeaderboardEntry,
    PerformanceTracker,
)


def _grade(
    agent_id: str = "agent-1",
    task_id: str = "task-1",
    grade: GradeLevel = GradeLevel.GOOD,
    criteria: str = "code quality",
    reasoning: str = "Clean implementation",
    graded_by: str = "judge-llm",
    timestamp: datetime | None = None,
) -> AgentGrade:
    kwargs: dict[str, object] = {
        "agent_id": agent_id,
        "task_id": task_id,
        "grade": grade,
        "criteria": criteria,
        "reasoning": reasoning,
        "graded_by": graded_by,
    }
    if timestamp is not None:
        kwargs["timestamp"] = timestamp
    return AgentGrade(**kwargs)  # type: ignore[arg-type]


class TestAgentGrade:
    def test_frozen(self) -> None:
        g = _grade()
        assert g.agent_id == "agent-1"
        assert g.grade == GradeLevel.GOOD

    def test_grade_level_values(self) -> None:
        assert list(GradeLevel) == [
            "excellent",
            "good",
            "acceptable",
            "poor",
            "failing",
        ]


class TestPerformanceTracker:
    def test_record_and_get_grades(self) -> None:
        tracker = PerformanceTracker()
        g1 = _grade(task_id="t1")
        g2 = _grade(task_id="t2", grade=GradeLevel.EXCELLENT)
        tracker.record_grade(g1)
        tracker.record_grade(g2)
        grades = tracker.get_grades("agent-1")
        assert len(grades) == 2

    def test_get_grades_filters_by_agent(self) -> None:
        tracker = PerformanceTracker()
        tracker.record_grade(_grade(agent_id="a"))
        tracker.record_grade(_grade(agent_id="b"))
        assert len(tracker.get_grades("a")) == 1

    def test_get_grades_empty(self) -> None:
        tracker = PerformanceTracker()
        assert tracker.get_grades("missing") == []

    def test_get_average_grade(self) -> None:
        tracker = PerformanceTracker()
        tracker.record_grade(_grade(grade=GradeLevel.EXCELLENT))  # 5
        tracker.record_grade(_grade(grade=GradeLevel.POOR))  # 2
        avg = tracker.get_average_grade("agent-1")
        assert avg == 3.5

    def test_get_average_grade_none_when_empty(self) -> None:
        tracker = PerformanceTracker()
        assert tracker.get_average_grade("missing") is None

    def test_get_leaderboard(self) -> None:
        tracker = PerformanceTracker()
        tracker.record_grade(_grade(agent_id="a", grade=GradeLevel.EXCELLENT))
        tracker.record_grade(_grade(agent_id="b", grade=GradeLevel.POOR))
        tracker.record_grade(_grade(agent_id="a", grade=GradeLevel.GOOD))
        board = tracker.get_leaderboard()
        assert len(board) == 2
        assert board[0].agent_id == "a"
        assert board[0].average_score == 4.5
        assert board[0].total_grades == 2
        assert board[1].agent_id == "b"

    def test_leaderboard_empty(self) -> None:
        tracker = PerformanceTracker()
        assert tracker.get_leaderboard() == []

    def test_grades_sorted_by_timestamp(self) -> None:
        tracker = PerformanceTracker()
        t1 = datetime(2026, 1, 2, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, tzinfo=UTC)
        tracker.record_grade(_grade(task_id="later", timestamp=t1))
        tracker.record_grade(_grade(task_id="earlier", timestamp=t2))
        grades = tracker.get_grades("agent-1")
        assert grades[0].task_id == "earlier"
        assert grades[1].task_id == "later"

    def test_leaderboard_entry_frozen(self) -> None:
        entry = LeaderboardEntry(agent_id="x", average_score=4.0, total_grades=1)
        assert entry.agent_id == "x"
