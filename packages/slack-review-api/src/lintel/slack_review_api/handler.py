"""SlackReviewHandler — orchestrates PR review from Slack trigger."""

from __future__ import annotations

from dataclasses import replace
import re
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.repos.github_provider import GitHubRepoProvider
    from lintel.slack_review_api.store import InMemorySlackReviewStore, SlackReviewRequest

logger = structlog.get_logger()

REVIEW_SYSTEM_PROMPT = """\
You are a pragmatic senior code reviewer. Review the following PR diff for:
1. Correctness — does the code do what it should?
2. Security — any obvious vulnerabilities (injection, secrets, etc.)?
3. Quality — reasonable code structure and naming?

Be concise. Provide:
- VERDICT: APPROVE or REQUEST_CHANGES
- Summary of findings
- Specific issues (if any)

Default to APPROVE unless there is a real problem.
"""

PR_PATTERN = re.compile(r"(?:PR|pr|pull request)\s*#?(\d+)", re.IGNORECASE)


def parse_pr_number(text: str) -> int | None:
    """Extract PR number from Slack message text like 'review PR #42'."""
    match = PR_PATTERN.search(text)
    return int(match.group(1)) if match else None


class SlackReviewHandler:
    """Orchestrates standalone PR review triggered from Slack."""

    def __init__(
        self,
        github_provider: GitHubRepoProvider,
        review_store: InMemorySlackReviewStore,
    ) -> None:
        self._github = github_provider
        self._store = review_store

    async def run_review(self, review: SlackReviewRequest) -> dict[str, Any]:
        """Fetch PR diff, run review, return result dict."""
        from dataclasses import asdict

        # Mark reviewing
        review = replace(review, status="reviewing")
        await self._store.update(review)

        try:
            diff_text = await self._github.get_pr_diff(review.repo_url, review.pr_number)
        except Exception:
            logger.exception(
                "slack_review_fetch_diff_failed",
                pr_number=review.pr_number,
                repo_url=review.repo_url,
            )
            review = replace(review, status="failed", review_body="Failed to fetch PR diff.")
            await self._store.update(review)
            return asdict(review)

        if not diff_text.strip():
            review = replace(
                review,
                status="completed",
                verdict="approve",
                review_body="No changes in PR diff.",
            )
            await self._store.update(review)
            return asdict(review)

        # Truncate very large diffs
        if len(diff_text) > 50_000:
            diff_text = diff_text[:50_000] + "\n... (diff truncated)"

        # Build review body from diff analysis (simple heuristic review)
        review_body, verdict = self._analyse_diff(diff_text)

        review = replace(
            review,
            status="completed",
            verdict=verdict,
            review_body=review_body,
        )
        await self._store.update(review)

        # Post review as GitHub PR comment
        try:
            await self._github.add_comment(
                review.repo_url,
                review.pr_number,
                f"**Lintel Review** ({verdict.upper()})\n\n{review_body}",
            )
        except Exception:
            logger.warning(
                "slack_review_post_comment_failed",
                pr_number=review.pr_number,
            )

        return asdict(review)

    def _analyse_diff(self, diff_text: str) -> tuple[str, str]:
        """Analyse diff and return (review_body, verdict).

        This is a lightweight structural analysis. When an agent runtime is
        available, this will be replaced by an LLM-powered review.
        """
        lines = diff_text.splitlines()
        added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
        files_changed = sum(1 for ln in lines if ln.startswith("diff --git"))

        summary_parts = [
            f"Reviewed PR diff: {files_changed} file(s) changed, +{added}/-{removed} lines.",
        ]

        # Check for common issues
        issues: list[str] = []
        for i, line in enumerate(lines, 1):
            lower = line.lower()
            secret_kws = ("password", "secret", "api_key", "token")
            safe_kws = ("test", "mock", "example")
            if (
                any(kw in lower for kw in secret_kws)
                and line.startswith("+")
                and not any(s in lower for s in safe_kws)
            ):
                issues.append(f"- Line {i}: possible secret/credential in added code")

        verdict = "approve"
        if issues:
            summary_parts.append("\n**Potential issues:**")
            summary_parts.extend(issues[:10])
            if len(issues) > 3:
                verdict = "request_changes"

        return "\n".join(summary_parts), verdict

    def format_slack_message(self, result: dict[str, Any]) -> str:
        """Format review result as a Slack message."""
        verdict = result.get("verdict", "unknown")
        emoji = ":white_check_mark:" if verdict == "approve" else ":warning:"
        body = result.get("review_body", "No review body.")
        pr_number = result.get("pr_number", "?")
        return f"{emoji} *Review for PR #{pr_number}*\n\n{body}"
