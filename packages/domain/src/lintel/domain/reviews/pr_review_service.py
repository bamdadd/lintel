"""Automated PR review service — fetches diff, scores files, posts feedback."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from lintel.domain.reviews.engine import ReviewEngine
from lintel.domain.reviews.models import (
    Finding,
    FindingSeverity,
    PRReviewResult,
    PRReviewVerdict,
    ReviewDimension,
    ReviewPolicy,
)

if TYPE_CHECKING:
    from lintel.repos.protocols import RepoProvider
    from lintel.repos.types import InlineComment, PRFile, ReviewVerdict

logger = structlog.get_logger()

# File extensions to skip during review
_SKIP_EXTENSIONS = frozenset({
    ".lock", ".sum", ".min.js", ".min.css", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
})

_MAX_PATCH_LINES = 500


class PRReviewService:
    """Orchestrates automated PR review: fetch diff, score, post feedback.

    Uses the existing :class:`ReviewEngine` for per-file scoring and
    aggregation, then translates findings into GitHub review comments
    and a summary verdict.
    """

    def __init__(
        self,
        repo_provider: RepoProvider,
        policy: ReviewPolicy | None = None,
    ) -> None:
        self._provider = repo_provider
        self._policy = policy or ReviewPolicy()
        self._engine = ReviewEngine(self._policy)

    async def review_pr(
        self,
        repo_url: str,
        pr_number: int,
        *,
        head_sha: str = "",
        post_review: bool = True,
        create_check: bool = True,
    ) -> PRReviewResult:
        """Run an automated review on a pull request.

        1. Fetch changed files
        2. Analyse each file's patch for issues
        3. Aggregate into a verdict
        4. Optionally post a GitHub review and check run
        """
        logger.info(
            "pr_review.start",
            repo_url=repo_url,
            pr_number=pr_number,
        )

        check_run_id = ""
        if create_check and head_sha:
            check_run_id = await self._provider.create_check_run(
                repo_url,
                head_sha,
                "lintel-review",
                status="in_progress",
                title="Lintel automated review",
                summary="Review in progress...",
            )

        pr_files = await self._provider.get_pr_files(repo_url, pr_number)
        reviewable = [f for f in pr_files if self._should_review(f)]

        file_reviews = []
        for pr_file in reviewable:
            findings = self._analyse_patch(pr_file)
            scores = self._estimate_scores(findings)
            fr = self._engine.review_file(pr_file.filename, scores, findings)
            file_reviews.append(fr)

        review = self._engine.aggregate(file_reviews)
        passes = self._engine.passes_policy(review)

        critical_count = sum(
            1 for fr in file_reviews
            for f in fr.findings
            if f.severity == FindingSeverity.CRITICAL
        )
        high_count = sum(
            1 for fr in file_reviews
            for f in fr.findings
            if f.severity == FindingSeverity.HIGH
        )

        # No reviewable files → clean pass
        no_findings = not file_reviews or review.total_findings == 0

        if critical_count > 0:
            verdict = PRReviewVerdict.FAIL
        elif high_count > 0 or (not no_findings and not passes):
            verdict = PRReviewVerdict.WARN
        else:
            verdict = PRReviewVerdict.PASS

        summary = self._format_summary(review, verdict, len(pr_files), len(reviewable))

        result = PRReviewResult(
            review_id=review.review_id,
            repo_url=repo_url,
            pr_number=pr_number,
            verdict=verdict,
            overall_score=review.overall_score,
            total_findings=review.total_findings,
            critical_count=critical_count,
            high_count=high_count,
            file_reviews=review.file_reviews,
            summary=summary,
        )

        if post_review:
            await self._post_review(repo_url, pr_number, result)

        if check_run_id:
            from lintel.repos.types import CheckRunConclusion

            conclusion = (
                CheckRunConclusion.SUCCESS if verdict == PRReviewVerdict.PASS
                else CheckRunConclusion.FAILURE if verdict == PRReviewVerdict.FAIL
                else CheckRunConclusion.NEUTRAL
            )
            await self._provider.update_check_run(
                repo_url,
                check_run_id,
                status="completed",
                conclusion=conclusion,
                title=f"Lintel review: {verdict.value}",
                summary=summary,
            )

        logger.info(
            "pr_review.complete",
            repo_url=repo_url,
            pr_number=pr_number,
            verdict=verdict.value,
            findings=review.total_findings,
        )
        return result

    # ------------------------------------------------------------------
    # Patch analysis
    # ------------------------------------------------------------------

    def _should_review(self, pr_file: PRFile) -> bool:
        """Filter out binary, generated, and non-reviewable files."""
        name = pr_file.filename.lower()
        if any(name.endswith(ext) for ext in _SKIP_EXTENSIONS):
            return False
        if pr_file.status == "removed":
            return False
        if not pr_file.patch:
            return False
        return True

    def _analyse_patch(self, pr_file: PRFile) -> list[Finding]:
        """Run heuristic checks on a file's patch to find common issues."""
        findings: list[Finding] = []
        lines = pr_file.patch.split("\n")

        if len(lines) > _MAX_PATCH_LINES:
            findings.append(Finding(
                dimension=ReviewDimension.MAINTAINABILITY,
                severity=FindingSeverity.MEDIUM,
                message=f"Large change ({len(lines)} patch lines) — consider splitting.",
            ))

        added_lines = [ln for ln in lines if ln.startswith("+") and not ln.startswith("+++")]
        for i, line in enumerate(added_lines):
            line_num = self._extract_line_number(lines, i)
            findings.extend(self._check_line(line, pr_file.filename, line_num))

        return findings

    def _check_line(
        self, line: str, filename: str, line_num: int | None
    ) -> list[Finding]:
        """Check a single added line for common issues."""
        findings: list[Finding] = []
        content = line[1:]  # strip the leading '+'

        # Security: hardcoded secrets
        if re.search(
            r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}',
            content,
            re.IGNORECASE,
        ):
            findings.append(Finding(
                dimension=ReviewDimension.SECURITY,
                severity=FindingSeverity.CRITICAL,
                message="Possible hardcoded secret detected.",
                line=line_num,
                suggestion="Use environment variables or a secrets manager.",
            ))

        # Security: SQL injection risk
        if re.search(r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE)\b.*\{', content, re.IGNORECASE):
            findings.append(Finding(
                dimension=ReviewDimension.SECURITY,
                severity=FindingSeverity.HIGH,
                message="Potential SQL injection via f-string interpolation.",
                line=line_num,
                suggestion="Use parameterised queries instead.",
            ))

        # Correctness: bare except
        if re.search(r'\bexcept\s*:', content):
            findings.append(Finding(
                dimension=ReviewDimension.CORRECTNESS,
                severity=FindingSeverity.MEDIUM,
                message="Bare `except:` catches all exceptions including KeyboardInterrupt.",
                line=line_num,
                suggestion="Catch a specific exception type.",
            ))

        # Maintainability: TODO/FIXME/HACK
        if re.search(r'\b(TODO|FIXME|HACK|XXX)\b', content):
            findings.append(Finding(
                dimension=ReviewDimension.MAINTAINABILITY,
                severity=FindingSeverity.LOW,
                message="TODO/FIXME marker found — track or resolve before merge.",
                line=line_num,
            ))

        # Performance: nested loops (simple heuristic)
        if filename.endswith(".py") and re.search(r'for\s+\w+\s+in\s+.*:\s*$', content):
            # Only flag if the file has multiple 'for' in added lines
            pass  # left as a placeholder for deeper analysis

        return findings

    def _extract_line_number(self, patch_lines: list[str], added_index: int) -> int | None:
        """Try to extract the target-side line number for an added line."""
        current_line = 0
        added_count = 0
        for raw in patch_lines:
            hunk_match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)', raw)
            if hunk_match:
                current_line = int(hunk_match.group(1))
                continue
            if raw.startswith("-"):
                continue
            if raw.startswith("+"):
                if added_count == added_index:
                    return current_line
                added_count += 1
            current_line += 1
        return None

    def _estimate_scores(
        self, findings: list[Finding]
    ) -> dict[ReviewDimension, float]:
        """Estimate dimension scores based on findings (10 = perfect, 0 = worst)."""
        scores: dict[ReviewDimension, float] = {d: 10.0 for d in ReviewDimension}
        severity_penalty = {
            FindingSeverity.INFO: 0.5,
            FindingSeverity.LOW: 1.0,
            FindingSeverity.MEDIUM: 2.0,
            FindingSeverity.HIGH: 3.5,
            FindingSeverity.CRITICAL: 5.0,
        }
        for f in findings:
            penalty = severity_penalty.get(f.severity, 1.0)
            scores[f.dimension] = max(0.0, scores[f.dimension] - penalty)
        return scores

    # ------------------------------------------------------------------
    # GitHub integration
    # ------------------------------------------------------------------

    def _format_summary(
        self,
        review: object,
        verdict: PRReviewVerdict,
        total_files: int,
        reviewed_files: int,
    ) -> str:
        """Format a markdown summary comment."""
        from lintel.domain.reviews.models import CodebaseReview

        assert isinstance(review, CodebaseReview)
        icon = {"pass": "\u2705", "warn": "\u26a0\ufe0f", "fail": "\u274c"}
        lines = [
            f"## {icon.get(verdict.value, '')} Lintel Review: **{verdict.value.upper()}**",
            "",
            f"**Score:** {review.overall_score}/10.0 | "
            f"**Findings:** {review.total_findings} | "
            f"**Files reviewed:** {reviewed_files}/{total_files}",
            "",
        ]

        if review.summary_scores:
            lines.append("### Dimension Scores")
            lines.append("| Dimension | Score |")
            lines.append("|-----------|-------|")
            for dim, score in review.summary_scores.items():
                lines.append(f"| {dim.value.title()} | {score}/10 |")
            lines.append("")

        if review.critical_files:
            lines.append("### Critical Files")
            for fr in review.critical_files:
                lines.append(f"- `{fr.file_path}` ({len(fr.findings)} findings)")
            lines.append("")

        return "\n".join(lines)

    async def _post_review(
        self,
        repo_url: str,
        pr_number: int,
        result: PRReviewResult,
    ) -> None:
        """Post the review as a GitHub PR review with inline comments."""
        from lintel.repos.types import InlineComment, ReviewVerdict

        inline_comments: list[InlineComment] = []
        for fr in result.file_reviews:
            for finding in fr.findings:
                if finding.line is not None and finding.severity in (
                    FindingSeverity.MEDIUM,
                    FindingSeverity.HIGH,
                    FindingSeverity.CRITICAL,
                ):
                    body = f"**[{finding.severity.value.upper()}]** {finding.message}"
                    if finding.suggestion:
                        body += f"\n\n> {finding.suggestion}"
                    inline_comments.append(InlineComment(
                        path=fr.file_path,
                        line=finding.line,
                        body=body,
                    ))

        if result.verdict == PRReviewVerdict.FAIL:
            gh_verdict = ReviewVerdict.REQUEST_CHANGES
        elif result.verdict == PRReviewVerdict.WARN:
            gh_verdict = ReviewVerdict.COMMENT
        else:
            gh_verdict = ReviewVerdict.APPROVE

        await self._provider.create_review(
            repo_url,
            pr_number,
            result.summary,
            gh_verdict,
            inline_comments or None,
        )
