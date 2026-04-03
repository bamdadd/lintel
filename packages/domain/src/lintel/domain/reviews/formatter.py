"""Converts a CodebaseReview into GitHub PR review format."""

from __future__ import annotations

from typing import Any

from lintel.domain.reviews.models import (
    CodebaseReview,
    Finding,
    FindingSeverity,
    ReviewPolicy,
)

_SEVERITY_EMOJI: dict[FindingSeverity, str] = {
    FindingSeverity.INFO: "[info]",
    FindingSeverity.LOW: "[low]",
    FindingSeverity.MEDIUM: "[warn]",
    FindingSeverity.HIGH: "[high]",
    FindingSeverity.CRITICAL: "[critical]",
}


class PRReviewFormatter:
    """Converts a CodebaseReview into GitHub PR review format."""

    def format_review(
        self,
        review: CodebaseReview,
        policy: ReviewPolicy,
    ) -> dict[str, Any]:
        """Return ``{body, event, comments}`` for ``RepoProvider.create_review()``."""
        passes = _passes_policy(review, policy)
        event = "COMMENT" if passes else "REQUEST_CHANGES"

        body = self._build_summary(review, policy, passes)
        comments = self._build_inline_comments(review)

        return {"body": body, "event": event, "comments": comments}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        review: CodebaseReview,
        policy: ReviewPolicy,
        passes: bool,
    ) -> str:
        """Build the top-level review body with scores and summary findings."""
        lines: list[str] = []

        verdict = "PASS" if passes else "FAIL"
        lines.append(f"## Automated Code Review — {verdict}")
        lines.append("")
        lines.append(f"**Overall score:** {review.overall_score:.1f} / 10.0")
        lines.append(
            f"**Threshold:** {policy.min_score_threshold:.1f} | "
            f"**Files reviewed:** {len(review.file_reviews)} | "
            f"**Total findings:** {review.total_findings}"
        )
        lines.append("")

        # Dimension breakdown
        if review.summary_scores:
            lines.append("### Dimension Scores")
            lines.append("")
            lines.append("| Dimension | Score |")
            lines.append("|-----------|-------|")
            for dim, score in sorted(review.summary_scores.items(), key=lambda x: x[0].value):
                lines.append(f"| {dim.value.title()} | {score:.1f} |")
            lines.append("")

        # Findings without line numbers go in the summary body
        orphan_findings = self._collect_orphan_findings(review)
        if orphan_findings:
            lines.append("### Findings (no line reference)")
            lines.append("")
            for file_path, finding in orphan_findings:
                emoji = _SEVERITY_EMOJI.get(finding.severity, "")
                lines.append(
                    f"- {emoji} **{file_path}** [{finding.severity.value}] "
                    f"({finding.dimension.value}): {finding.message}"
                )
                if finding.suggestion:
                    lines.append(f"  - Suggestion: {finding.suggestion}")
            lines.append("")

        return "\n".join(lines)

    def _build_inline_comments(
        self,
        review: CodebaseReview,
    ) -> list[dict[str, Any]]:
        """Convert findings with line numbers to inline PR review comments."""
        comments: list[dict[str, Any]] = []
        for fr in review.file_reviews:
            for finding in fr.findings:
                if finding.line is None:
                    continue
                body = self._format_finding(finding)
                comments.append(
                    {
                        "path": fr.file_path,
                        "line": finding.line,
                        "body": body,
                    }
                )
        return comments

    def _format_finding(self, finding: Finding) -> str:
        """Format a single finding as a markdown comment body."""
        emoji = _SEVERITY_EMOJI.get(finding.severity, "")
        parts = [
            f"{emoji} **[{finding.severity.value.upper()}]** "
            f"({finding.dimension.value}): {finding.message}",
        ]
        if finding.suggestion:
            parts.append(f"\n**Suggestion:** {finding.suggestion}")
        return "".join(parts)

    def _collect_orphan_findings(
        self,
        review: CodebaseReview,
    ) -> list[tuple[str, Finding]]:
        """Collect findings that have no line number (cannot be inline)."""
        result: list[tuple[str, Finding]] = []
        for fr in review.file_reviews:
            for finding in fr.findings:
                if finding.line is None:
                    result.append((fr.file_path, finding))
        return result


def _passes_policy(review: CodebaseReview, policy: ReviewPolicy) -> bool:
    """Check whether a review passes policy thresholds."""
    if review.overall_score < policy.min_score_threshold:
        return False
    return not (policy.fail_on_critical and review.critical_files)
