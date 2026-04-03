"""Tests for AutoReviewService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.domain.reviews.auto_review import AutoReviewService
from lintel.domain.reviews.engine import ReviewEngine
from lintel.domain.reviews.formatter import PRReviewFormatter
from lintel.domain.reviews.models import ReviewPolicy

SAMPLE_DIFF = """\
diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
 import os
+import sys

 def main():
"""


def _make_repo(diff_text: str = SAMPLE_DIFF) -> MagicMock:
    """Create a MagicMock RepoProvider with async methods."""
    repo = MagicMock()
    repo.get_pr_diff = AsyncMock(return_value=diff_text)
    repo.create_review = AsyncMock()
    return repo


class TestAutoReviewService:
    def _make_service(
        self,
        diff_text: str = SAMPLE_DIFF,
        policy: ReviewPolicy | None = None,
    ) -> tuple[AutoReviewService, MagicMock]:
        repo = _make_repo(diff_text)
        engine = ReviewEngine(policy or ReviewPolicy())
        formatter = PRReviewFormatter()
        service = AutoReviewService(engine, repo, formatter)
        return service, repo

    async def test_fetches_diff(self) -> None:
        service, repo = self._make_service()
        await service.review_pull_request("https://github.com/org/repo", 42)
        repo.get_pr_diff.assert_awaited_once_with("https://github.com/org/repo", 42)

    async def test_posts_review(self) -> None:
        service, repo = self._make_service()
        await service.review_pull_request("https://github.com/org/repo", 42)
        repo.create_review.assert_awaited_once()
        call_args = repo.create_review.call_args
        assert call_args.args[0] == "https://github.com/org/repo"
        assert call_args.args[1] == 42

    async def test_returns_codebase_review(self) -> None:
        service, _ = self._make_service()
        review = await service.review_pull_request("https://github.com/org/repo", 42)
        assert review.overall_score > 0
        assert len(review.file_reviews) == 1
        assert review.file_reviews[0].file_path == "src/app.py"

    async def test_empty_diff_returns_empty_review(self) -> None:
        service, repo = self._make_service(diff_text="")
        review = await service.review_pull_request("https://github.com/org/repo", 42)
        assert review.overall_score == 0.0
        assert len(review.file_reviews) == 0
        # No review posted for empty diff
        repo.create_review.assert_not_awaited()

    async def test_custom_policy(self) -> None:
        policy = ReviewPolicy(min_score_threshold=9.0)
        service, repo = self._make_service(policy=policy)
        await service.review_pull_request(
            "https://github.com/org/repo",
            42,
            policy=policy,
        )
        # The review should have been posted
        repo.create_review.assert_awaited_once()
        # Review body should mention REQUEST_CHANGES since 7.0 < 9.0
        call_args = repo.create_review.call_args
        body = call_args.args[2]
        assert "FAIL" in body

    async def test_multiple_files_in_diff(self) -> None:
        multi_diff = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+new
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1 +1 @@
-old
+new
"""
        service, _ = self._make_service(diff_text=multi_diff)
        review = await service.review_pull_request("https://github.com/org/repo", 42)
        assert len(review.file_reviews) == 2
        paths = {fr.file_path for fr in review.file_reviews}
        assert paths == {"a.py", "b.py"}
