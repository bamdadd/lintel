"""Orchestrates automated PR review: fetch diff, analyze, post review."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.domain.reviews.diff_parser import parse_diff
from lintel.domain.reviews.formatter import PRReviewFormatter
from lintel.domain.reviews.models import (
    CodebaseReview,
    ReviewDimension,
    ReviewPolicy,
)

if TYPE_CHECKING:
    from lintel.domain.reviews.engine import ReviewEngine
    from lintel.repos.protocols import RepoProvider
    from lintel.repos.types import ReviewVerdict

logger = structlog.get_logger()


class AutoReviewService:
    """Orchestrates automated PR review: fetch diff -> analyze -> post review."""

    def __init__(
        self,
        review_engine: ReviewEngine,
        repo_provider: RepoProvider,
        formatter: PRReviewFormatter,
    ) -> None:
        self._engine = review_engine
        self._repo = repo_provider
        self._formatter = formatter

    async def review_pull_request(
        self,
        repo_url: str,
        pr_number: int,
        *,
        policy: ReviewPolicy | None = None,
    ) -> CodebaseReview:
        """Run automated review on a PR and post findings as a GitHub review.

        1. Fetch PR diff via repo_provider.get_pr_diff()
        2. Parse diff into file changes
        3. For each changed file, run review_engine.review_file()
        4. Aggregate into a CodebaseReview
        5. Format and post via repo_provider.create_review()
        6. Return the CodebaseReview
        """
        effective_policy = policy or self._engine.policy

        logger.info(
            "auto_review_started",
            repo_url=repo_url,
            pr_number=pr_number,
        )

        # 1. Fetch diff
        diff_text = await self._repo.get_pr_diff(repo_url, pr_number)

        # 2. Parse diff
        diff_files = parse_diff(diff_text)

        if not diff_files:
            logger.info("auto_review_no_files", pr_number=pr_number)
            review = self._engine.aggregate([])
            return review

        # 3. Review each file
        file_reviews = []
        for df in diff_files:
            # Provide neutral placeholder scores — a real integration would
            # call an LLM here. For now, score based on diff heuristics.
            scores = _placeholder_scores(df)
            findings: list[Any] = []
            fr = self._engine.review_file(df.path, scores, findings)
            file_reviews.append(fr)

        # 4. Aggregate
        review = self._engine.aggregate(file_reviews)

        # 5. Format
        formatted = self._formatter.format_review(review, effective_policy)

        # 6. Post review
        from lintel.repos.types import InlineComment, ReviewVerdict

        verdict = ReviewVerdict(formatted["event"])
        raw_comments = formatted.get("comments", [])
        inline_comments: list[InlineComment] = [
            InlineComment(path=c["path"], line=c["line"], body=c["body"])
            for c in raw_comments
        ] if raw_comments else []

        await self._repo.create_review(
            repo_url,
            pr_number,
            formatted["body"],
            verdict,
            inline_comments or None,
        )

        logger.info(
            "auto_review_completed",
            pr_number=pr_number,
            overall_score=review.overall_score,
            total_findings=review.total_findings,
        )

        return review


def _placeholder_scores(
    df: Any,
) -> dict[ReviewDimension, float]:
    """Generate neutral placeholder scores for a diff file.

    In a real implementation this would be replaced by LLM-based analysis.
    """
    return {d: 7.0 for d in ReviewDimension}
