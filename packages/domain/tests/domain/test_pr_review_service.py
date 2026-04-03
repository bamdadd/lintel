"""Tests for PRReviewService — automated PR review orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.domain.reviews.models import (
    FindingSeverity,
    PRReviewVerdict,
)
from lintel.domain.reviews.pr_review_service import PRReviewService
from lintel.repos.types import CheckRunConclusion, PRFile, ReviewVerdict


def _make_provider() -> MagicMock:
    """Create a mock RepoProvider."""
    provider = MagicMock()
    provider.get_pr_files = AsyncMock(return_value=[])
    provider.create_review = AsyncMock(return_value="1")
    provider.create_check_run = AsyncMock(return_value="check-1")
    provider.update_check_run = AsyncMock()
    return provider


def _make_pr_file(
    filename: str,
    patch: str = "",
    status: str = "modified",
    additions: int = 5,
) -> PRFile:
    return PRFile(
        filename=filename,
        status=status,
        additions=additions,
        deletions=0,
        patch=patch,
    )


REPO_URL = "https://github.com/org/repo"


class TestPRReviewServiceBasic:
    async def test_empty_pr_returns_pass(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = []
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 1, post_review=False, create_check=False)
        assert result.verdict == PRReviewVerdict.PASS
        assert result.total_findings == 0
        assert result.pr_number == 1

    async def test_clean_file_returns_pass(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file("src/clean.py", "@@ -1,3 +1,5 @@\n+x = 1\n+y = 2"),
        ]
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 2, post_review=False, create_check=False)
        assert result.verdict == PRReviewVerdict.PASS
        assert result.total_findings == 0

    async def test_skips_binary_and_removed_files(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file("logo.png", "binary data"),
            _make_pr_file("old.py", "@@ -1 +0,0 @@\n-deleted", status="removed"),
            _make_pr_file("styles.min.css", ".a{color:red}"),
            _make_pr_file("go.lock", "dep=1.0"),
        ]
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 3, post_review=False, create_check=False)
        # All should be skipped, empty review
        assert result.verdict == PRReviewVerdict.PASS
        assert result.total_findings == 0


class TestPRReviewServiceFindings:
    async def test_hardcoded_secret_triggers_critical(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file(
                "config.py",
                '@@ -1,1 +1,2 @@\n+password = "super_secret_password123"',
            ),
        ]
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 4, post_review=False, create_check=False)
        assert result.verdict == PRReviewVerdict.FAIL
        assert result.critical_count >= 1
        # Check the finding message
        findings = [f for fr in result.file_reviews for f in fr.findings]
        secret_findings = [f for f in findings if f.severity == FindingSeverity.CRITICAL]
        assert len(secret_findings) >= 1
        assert "secret" in secret_findings[0].message.lower()

    async def test_sql_injection_triggers_high(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file(
                "db.py",
                '@@ -1,1 +1,2 @@\n+query = f"SELECT * FROM users WHERE id = {user_id}"',
            ),
        ]
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 5, post_review=False, create_check=False)
        assert result.high_count >= 1
        assert result.verdict in (PRReviewVerdict.WARN, PRReviewVerdict.FAIL)

    async def test_bare_except_triggers_medium(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file(
                "handler.py",
                "@@ -1,1 +1,3 @@\n+try:\n+    do_thing()\n+except:",
            ),
        ]
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 6, post_review=False, create_check=False)
        assert result.total_findings >= 1
        findings = [f for fr in result.file_reviews for f in fr.findings]
        assert any(f.severity == FindingSeverity.MEDIUM for f in findings)

    async def test_todo_marker_triggers_low(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file(
                "main.py",
                "@@ -1,1 +1,2 @@\n+# TODO: fix this later",
            ),
        ]
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 7, post_review=False, create_check=False)
        findings = [f for fr in result.file_reviews for f in fr.findings]
        assert any(f.severity == FindingSeverity.LOW for f in findings)


class TestPRReviewServiceGitHubIntegration:
    async def test_posts_review_with_inline_comments(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file(
                "config.py",
                '@@ -1,1 +1,2 @@\n+api_key = "sk-1234567890abcdef"',
            ),
        ]
        svc = PRReviewService(provider)
        await svc.review_pr(REPO_URL, 8, post_review=True, create_check=False)

        provider.create_review.assert_awaited_once()
        call_args = provider.create_review.call_args
        assert call_args.args[0] == REPO_URL
        assert call_args.args[1] == 8
        # Verdict should map to REQUEST_CHANGES for FAIL
        assert call_args.args[3] == ReviewVerdict.REQUEST_CHANGES

    async def test_creates_and_updates_check_run(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = []
        svc = PRReviewService(provider)
        await svc.review_pr(REPO_URL, 9, head_sha="abc123", post_review=False, create_check=True)

        provider.create_check_run.assert_awaited_once()
        provider.update_check_run.assert_awaited_once()
        update_args = provider.update_check_run.call_args
        assert update_args.kwargs.get("conclusion") == CheckRunConclusion.SUCCESS

    async def test_check_run_failure_on_critical(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file(
                "secrets.py",
                '@@ -1,1 +1,2 @@\n+secret = "my_super_duper_secret_value"',
            ),
        ]
        svc = PRReviewService(provider)
        await svc.review_pr(REPO_URL, 10, head_sha="def456", post_review=False, create_check=True)

        update_args = provider.update_check_run.call_args
        assert update_args.kwargs.get("conclusion") == CheckRunConclusion.FAILURE

    async def test_no_check_run_without_head_sha(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = []
        svc = PRReviewService(provider)
        await svc.review_pr(REPO_URL, 11, post_review=False, create_check=True)
        provider.create_check_run.assert_not_awaited()


class TestPRReviewServiceSummary:
    async def test_summary_contains_verdict(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = []
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 12, post_review=False, create_check=False)
        assert "PASS" in result.summary
        assert "Lintel Review" in result.summary

    async def test_summary_contains_dimension_scores(self) -> None:
        provider = _make_provider()
        provider.get_pr_files.return_value = [
            _make_pr_file("app.py", "@@ -1,1 +1,2 @@\n+# TODO: fix"),
        ]
        svc = PRReviewService(provider)
        result = await svc.review_pr(REPO_URL, 13, post_review=False, create_check=False)
        assert "Dimension" in result.summary
