"""Tests for GitHubRepoProvider PR review methods (get_pr_files, create_review, check runs)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from lintel.repos.github_provider import GitHubRepoProvider
from lintel.repos.types import CheckRunConclusion, InlineComment, ReviewVerdict

REPO_URL = "https://github.com/org/repo"


class TestGetPRFiles:
    async def test_returns_pr_files(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = [
                {
                    "filename": "src/main.py",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 3,
                    "patch": "@@ -1,3 +1,10 @@\n+new line",
                },
                {
                    "filename": "tests/test_main.py",
                    "status": "added",
                    "additions": 20,
                    "deletions": 0,
                    "patch": "@@ -0,0 +1,20 @@\n+import pytest",
                },
            ]
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp

            files = await provider.get_pr_files(REPO_URL, 42)
            assert len(files) == 2
            assert files[0].filename == "src/main.py"
            assert files[0].status == "modified"
            assert files[0].additions == 10
            assert files[0].deletions == 3
            assert files[0].patch.startswith("@@")
            assert files[1].filename == "tests/test_main.py"
            assert files[1].status == "added"

    async def test_empty_pr(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = []
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp

            files = await provider.get_pr_files(REPO_URL, 1)
            assert files == []


class TestCreateReview:
    async def test_create_review_comment_only(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id": 999}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp

            review_id = await provider.create_review(
                REPO_URL, 42, "Looks good!", ReviewVerdict.APPROVE
            )
            assert review_id == "999"
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["event"] == "APPROVE"
            assert payload["body"] == "Looks good!"
            assert "comments" not in payload

    async def test_create_review_with_inline_comments(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id": 1000}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp

            comments = [
                InlineComment(path="src/main.py", line=10, body="Missing type hint"),
                InlineComment(path="src/main.py", line=25, body="Potential SQL injection"),
            ]
            review_id = await provider.create_review(
                REPO_URL, 42, "Issues found", ReviewVerdict.REQUEST_CHANGES, comments
            )
            assert review_id == "1000"
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["event"] == "REQUEST_CHANGES"
            assert len(payload["comments"]) == 2
            assert payload["comments"][0]["path"] == "src/main.py"
            assert payload["comments"][0]["line"] == 10

    async def test_create_review_posts_to_correct_url(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id": 1}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp

            await provider.create_review(REPO_URL, 42, "LGTM", ReviewVerdict.APPROVE)
            call_args = mock_client.post.call_args
            assert "/pulls/42/reviews" in call_args.args[0]


class TestCreateCheckRun:
    async def test_create_check_run_in_progress(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id": 5555}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp

            check_id = await provider.create_check_run(REPO_URL, "abc123sha", "lintel-review")
            assert check_id == "5555"
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["name"] == "lintel-review"
            assert payload["head_sha"] == "abc123sha"
            assert payload["status"] == "in_progress"

    async def test_create_check_run_with_output(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id": 6666}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp

            check_id = await provider.create_check_run(
                REPO_URL,
                "abc123sha",
                "lintel-review",
                status="completed",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Review passed",
                summary="All checks passed",
            )
            assert check_id == "6666"
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["conclusion"] == "success"
            assert payload["output"]["title"] == "Review passed"


class TestUpdateCheckRun:
    async def test_update_check_run(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_client.patch.return_value = mock_resp

            await provider.update_check_run(
                REPO_URL,
                "5555",
                status="completed",
                conclusion=CheckRunConclusion.FAILURE,
                title="Review failed",
                summary="2 critical findings",
            )
            mock_client.patch.assert_called_once()
            payload = mock_client.patch.call_args.kwargs["json"]
            assert payload["conclusion"] == "failure"
            assert payload["output"]["summary"] == "2 critical findings"


class TestGetPrDiff:
    async def test_get_pr_diff_returns_text(self) -> None:
        provider = GitHubRepoProvider("tok")
        diff_text = (
            "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new"
        )
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.text = diff_text
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp

            result = await provider.get_pr_diff(REPO_URL, 42)
            assert result == diff_text

    async def test_get_pr_diff_uses_diff_accept_header(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.text = ""
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp

            await provider.get_pr_diff(REPO_URL, 42)
            call_kwargs = mock_client.get.call_args.kwargs
            assert call_kwargs["headers"]["Accept"] == "application/vnd.github.v3.diff"

    async def test_get_pr_diff_correct_url(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.text = ""
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp

            await provider.get_pr_diff(REPO_URL, 99)
            call_args = mock_client.get.call_args
            assert "/pulls/99" in call_args.args[0]
