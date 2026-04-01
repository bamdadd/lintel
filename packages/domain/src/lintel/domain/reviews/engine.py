"""Review engine that orchestrates codebase reviews (REQ-F006)."""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

import structlog

from lintel.domain.reviews.models import (
    CodebaseReview,
    FileReview,
    Finding,
    ReviewDimension,
)

if TYPE_CHECKING:
    from lintel.domain.reviews.models import ReviewPolicy

logger = structlog.get_logger()


class ReviewEngine:
    """Orchestrates multi-dimensional codebase reviews.

    The engine scores files across all configured dimensions, aggregates
    findings, and produces a structured :class:`CodebaseReview` report.
    """

    def __init__(self, policy: ReviewPolicy) -> None:
        self._policy = policy

    @property
    def policy(self) -> ReviewPolicy:
        """Return the active review policy."""
        return self._policy

    def review_file(
        self,
        file_path: str,
        dimension_scores: dict[ReviewDimension, float],
        findings: list[Finding],
    ) -> FileReview:
        """Build a :class:`FileReview` from raw scores and findings.

        Truncates findings to ``policy.max_findings_per_file`` and computes
        a weighted overall score using the policy weights.
        """
        # Clamp scores to [0, 10]
        clamped: dict[ReviewDimension, float] = {
            d: max(0.0, min(10.0, s))
            for d, s in dimension_scores.items()
            if d in self._policy.dimensions
        }

        # Fill missing dimensions with 0
        for dim in self._policy.dimensions:
            if dim not in clamped:
                clamped[dim] = 0.0

        truncated = findings[: self._policy.max_findings_per_file]

        overall = self._weighted_score(clamped)

        return FileReview(
            file_path=file_path,
            dimension_scores=clamped,
            findings=tuple(truncated),
            overall_score=round(overall, 2),
        )

    def aggregate(self, file_reviews: list[FileReview]) -> CodebaseReview:
        """Aggregate multiple file reviews into a :class:`CodebaseReview`."""
        if not file_reviews:
            return CodebaseReview(
                review_id=uuid.uuid4().hex,
                file_reviews=(),
                summary_scores={d: 0.0 for d in self._policy.dimensions},
                overall_score=0.0,
            )

        summary: dict[ReviewDimension, float] = {}
        for dim in self._policy.dimensions:
            scores = [fr.dimension_scores.get(dim, 0.0) for fr in file_reviews]
            summary[dim] = round(sum(scores) / len(scores), 2)

        overall = round(sum(fr.overall_score for fr in file_reviews) / len(file_reviews), 2)

        return CodebaseReview(
            review_id=uuid.uuid4().hex,
            file_reviews=tuple(file_reviews),
            summary_scores=summary,
            overall_score=overall,
        )

    def passes_policy(self, review: CodebaseReview) -> bool:
        """Check whether a codebase review passes the active policy."""
        if review.overall_score < self._policy.min_score_threshold:
            return False
        return not (self._policy.fail_on_critical and review.critical_files)

    def findings_to_fix(self, review: CodebaseReview) -> list[Finding]:
        """Return all findings that meet the auto-fix severity threshold."""
        result: list[Finding] = []
        for fr in review.file_reviews:
            for finding in fr.findings:
                if self._policy.should_auto_fix(finding.severity):
                    result.append(finding)
        return result

    def generate_report(self, review: CodebaseReview) -> dict[str, object]:
        """Produce a structured report dict from a codebase review."""
        return {
            "review_id": review.review_id,
            "overall_score": review.overall_score,
            "summary_scores": {d.value: s for d, s in review.summary_scores.items()},
            "total_findings": review.total_findings,
            "critical_files": [fr.file_path for fr in review.critical_files],
            "files_below_threshold": [fr.file_path for fr in review.files_below_threshold],
            "passes_policy": self.passes_policy(review),
            "file_count": len(review.file_reviews),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _weighted_score(self, scores: dict[ReviewDimension, float]) -> float:
        """Compute a weighted average from dimension scores."""
        weights = self._policy.effective_weights()
        total_weight = sum(weights[d] for d in scores)
        if total_weight == 0:
            return 0.0
        return sum(scores[d] * weights[d] for d in scores) / total_weight
