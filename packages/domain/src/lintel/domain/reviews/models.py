"""Domain models for codebase review (REQ-F006)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ReviewDimension(StrEnum):
    """The five dimensions a file is scored against."""

    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    ARCHITECTURE = "architecture"


class FindingSeverity(StrEnum):
    """Severity level for individual findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Finding:
    """A single review finding within a file."""

    dimension: ReviewDimension
    severity: FindingSeverity
    message: str
    line: int | None = None
    suggestion: str = ""


@dataclass(frozen=True)
class FileReview:
    """Review result for a single file."""

    file_path: str
    dimension_scores: dict[ReviewDimension, float]
    findings: tuple[Finding, ...]
    overall_score: float

    @property
    def has_critical(self) -> bool:
        """Return True if any finding is CRITICAL severity."""
        return any(f.severity == FindingSeverity.CRITICAL for f in self.findings)

    @property
    def findings_by_dimension(self) -> dict[ReviewDimension, list[Finding]]:
        """Group findings by dimension."""
        result: dict[ReviewDimension, list[Finding]] = {}
        for finding in self.findings:
            result.setdefault(finding.dimension, []).append(finding)
        return result


@dataclass(frozen=True)
class CodebaseReview:
    """Aggregate review result across all files."""

    review_id: str
    file_reviews: tuple[FileReview, ...]
    summary_scores: dict[ReviewDimension, float]
    overall_score: float

    @property
    def files_below_threshold(self) -> list[FileReview]:
        """Return files scoring below 5.0 overall."""
        return [fr for fr in self.file_reviews if fr.overall_score < 5.0]

    @property
    def total_findings(self) -> int:
        """Total number of findings across all files."""
        return sum(len(fr.findings) for fr in self.file_reviews)

    @property
    def critical_files(self) -> list[FileReview]:
        """Files with at least one CRITICAL finding."""
        return [fr for fr in self.file_reviews if fr.has_critical]


@dataclass(frozen=True)
class ReviewPolicy:
    """Configuration controlling review thresholds and auto-fix behaviour."""

    min_score_threshold: float = 5.0
    auto_fix_min_severity: FindingSeverity = FindingSeverity.MEDIUM
    dimensions: tuple[ReviewDimension, ...] = tuple(ReviewDimension)
    max_findings_per_file: int = 50
    fail_on_critical: bool = True
    weights: dict[ReviewDimension, float] = field(default_factory=dict)

    def effective_weights(self) -> dict[ReviewDimension, float]:
        """Return dimension weights, defaulting to equal weight."""
        default_weight = 1.0 / len(self.dimensions)
        return {d: self.weights.get(d, default_weight) for d in self.dimensions}

    def should_auto_fix(self, severity: FindingSeverity) -> bool:
        """Return True if the severity warrants auto-fix."""
        severity_order = list(FindingSeverity)
        return severity_order.index(severity) >= severity_order.index(self.auto_fix_min_severity)


class PRReviewVerdict(StrEnum):
    """Overall verdict of an automated PR review."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class PRReviewResult:
    """Result of an automated pull request review."""

    review_id: str
    repo_url: str
    pr_number: int
    verdict: PRReviewVerdict
    overall_score: float
    total_findings: int
    critical_count: int
    high_count: int
    file_reviews: tuple[FileReview, ...]
    summary: str = ""
