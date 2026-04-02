"""Agent performance tracking with LLM-as-judge grading (REQ-F016)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class GradeLevel(StrEnum):
    """Quality grade assigned by an LLM judge."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILING = "failing"


# Numeric weights for averaging.
_GRADE_WEIGHTS: dict[GradeLevel, float] = {
    GradeLevel.EXCELLENT: 5.0,
    GradeLevel.GOOD: 4.0,
    GradeLevel.ACCEPTABLE: 3.0,
    GradeLevel.POOR: 2.0,
    GradeLevel.FAILING: 1.0,
}


@dataclass(frozen=True)
class AgentGrade:
    """An immutable record of a grade assigned to an agent for a specific task."""

    agent_id: str
    task_id: str
    grade: GradeLevel
    criteria: str
    reasoning: str
    graded_by: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class LeaderboardEntry:
    """A single row on the agent leaderboard."""

    agent_id: str
    average_score: float
    total_grades: int


class PerformanceTracker:
    """In-memory store for agent performance grades."""

    def __init__(self) -> None:
        self._grades: list[AgentGrade] = []

    def record_grade(self, grade: AgentGrade) -> None:
        """Append a grade to the tracker."""
        self._grades.append(grade)

    def get_grades(self, agent_id: str) -> list[AgentGrade]:
        """Return all grades for *agent_id*, ordered by timestamp."""
        return sorted(
            (g for g in self._grades if g.agent_id == agent_id),
            key=lambda g: g.timestamp,
        )

    def get_average_grade(self, agent_id: str) -> float | None:
        """Return the numeric average grade for *agent_id*, or ``None`` if no grades."""
        grades = self.get_grades(agent_id)
        if not grades:
            return None
        total = sum(_GRADE_WEIGHTS[g.grade] for g in grades)
        return total / len(grades)

    def get_leaderboard(self) -> list[LeaderboardEntry]:
        """Return agents ranked by average score (descending)."""
        agent_ids: set[str] = {g.agent_id for g in self._grades}
        entries: list[LeaderboardEntry] = []
        for aid in agent_ids:
            avg = self.get_average_grade(aid)
            if avg is not None:
                count = len(self.get_grades(aid))
                entries.append(
                    LeaderboardEntry(agent_id=aid, average_score=avg, total_grades=count),
                )
        return sorted(entries, key=lambda e: e.average_score, reverse=True)
