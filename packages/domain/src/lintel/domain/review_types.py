"""Review-and-improve domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ReviewDimension(StrEnum):
    """Five dimensions of code review analysis."""

    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    ARCHITECTURE = "architecture"


class ReviewSeverity(StrEnum):
    """Severity levels for review findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass(frozen=True)
class ReviewFinding:
    """A single finding from a review analysis."""

    message: str
    severity: ReviewSeverity = ReviewSeverity.INFO
    line_start: int | None = None
    line_end: int | None = None
    rule_id: str = ""
    suggestion: str = ""


@dataclass(frozen=True)
class PerFileScore:
    """Score for a single file in a single review dimension."""

    file_path: str
    dimension: ReviewDimension
    score: float = 0.0
    severity: ReviewSeverity = ReviewSeverity.INFO
    findings: tuple[ReviewFinding, ...] = ()


@dataclass(frozen=True)
class ReviewReport:
    """Structured review report with per-file scores across all dimensions."""

    report_id: str
    pipeline_run_id: str
    repo_id: str
    contributor_id: str = ""
    commit_shas: tuple[str, ...] = ()
    per_file_scores: tuple[PerFileScore, ...] = ()
    aggregate_scores: dict[str, float] = field(default_factory=dict)
    created_at: str = ""
    storage_backend: str = "postgres"


@dataclass(frozen=True)
class ReviewScoreRecord:
    """A single review score record for trend tracking."""

    score_id: str
    repo_id: str
    contributor_id: str = ""
    pipeline_run_id: str = ""
    dimension: ReviewDimension = ReviewDimension.CORRECTNESS
    score: float = 0.0
    severity: ReviewSeverity = ReviewSeverity.INFO
    recorded_at: str = ""
