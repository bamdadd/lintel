"""Test plan domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class TestCasePriority(StrEnum):
    """Priority level for a test case."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class TestCase:
    """A single test case within a test plan."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    steps: tuple[str, ...] = ()
    expected_result: str = ""
    priority: TestCasePriority = TestCasePriority.MEDIUM


@dataclass(frozen=True)
class TestPlan:
    """A test plan containing test cases and coverage targets."""

    id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    title: str = ""
    description: str = ""
    test_cases: tuple[TestCase, ...] = ()
    coverage_targets: tuple[str, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
    )
