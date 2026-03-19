"""Domain models for parsed artifacts, coverage, and quality gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TestCaseStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class QualityGateSeverity(StrEnum):
    ERROR = "error"
    WARN = "warn"


@dataclass(frozen=True)
class TestCase:
    """A single test case from a test suite."""

    name: str
    classname: str = ""
    status: TestCaseStatus = TestCaseStatus.PASSED
    duration_ms: int = 0
    message: str = ""
    output: str = ""


@dataclass(frozen=True)
class TestSuite:
    """A group of test cases (e.g. a test file or class)."""

    name: str
    tests: tuple[TestCase, ...] = ()
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int = 0


@dataclass(frozen=True)
class ParsedArtifact:
    """Structured result from parsing a test result artifact."""

    suites: tuple[TestSuite, ...] = ()
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int = 0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100.0


@dataclass(frozen=True)
class LineCoverage:
    """Coverage data for a single line."""

    line_number: int
    hit_count: int


@dataclass(frozen=True)
class CoverageFile:
    """Coverage data for a single source file."""

    path: str
    lines: tuple[LineCoverage, ...] = ()
    lines_covered: int = 0
    lines_total: int = 0
    branches_covered: int = 0
    branches_total: int = 0

    @property
    def line_rate(self) -> float:
        if self.lines_total == 0:
            return 0.0
        return self.lines_covered / self.lines_total


@dataclass(frozen=True)
class CoverageReport:
    """Aggregate coverage report across all files."""

    files: tuple[CoverageFile, ...] = ()
    line_rate: float = 0.0
    branch_rate: float = 0.0
    lines_covered: int = 0
    lines_total: int = 0
    branches_covered: int = 0
    branches_total: int = 0


@dataclass(frozen=True)
class QualityGateRule:
    """A configurable quality gate rule for a project."""

    rule_id: str
    project_id: str
    rule_type: str  # min_pass_rate, min_coverage, max_coverage_drop
    threshold: float
    severity: QualityGateSeverity = QualityGateSeverity.ERROR
    enabled: bool = True


@dataclass(frozen=True)
class QualityGateResult:
    """Result of evaluating a single quality gate rule."""

    rule_id: str
    rule_type: str
    passed: bool
    severity: QualityGateSeverity
    actual_value: float
    threshold_value: float
    message: str = ""
