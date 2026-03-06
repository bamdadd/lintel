"""Tests for the GitHub repo provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from lintel.infrastructure.repos.github_provider import GitHubRepoProvider


class TestGitHubRepoProvider:
    def _make_provider(self) -> GitHubRepoProvider:
        return GitHubRepoProvider(token="test-token", api_base="https://api.github.com")

    async def test_clone_calls_git(self) -> None:
        provider = self._make_provider()
        with patch.object(provider, "_run_git", new_callable=AsyncMock) as mock_git:
            await provider.clone("https://github.com/org/repo", "main", "/tmp/dest")
            mock_git.assert_awaited_once_with(
                "clone",
                "--branch",
                "main",
                "--depth",
                "1",
                "https://github.com/org/repo",
                "/tmp/dest",
            )

    async def test_create_branch_calls_git(self) -> None:
        provider = self._make_provider()
        with patch.object(provider, "_run_git", new_callable=AsyncMock) as mock_git:
            await provider.create_branch("https://github.com/org/repo", "/tmp/repo", "feature-1")
            mock_git.assert_awaited_once_with(
                "checkout",
                "-b",
                "feature-1",
                cwd="/tmp/repo",
            )

    async def test_commit_and_push_returns_sha(self) -> None:
        provider = self._make_provider()
        with patch.object(provider, "_run_git", new_callable=AsyncMock) as mock_git:
            mock_git.return_value = "abc123"
            sha = await provider.commit_and_push("/tmp/repo", "fix: bug", "feature-1")
            assert sha == "abc123"
            assert mock_git.call_count == 4  # add, commit, rev-parse, push

    async def test_create_pr_sends_post(self) -> None:
        provider = self._make_provider()
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.json.return_value = {"html_url": "https://github.com/org/repo/pull/1"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            url = await provider.create_pr(
                "https://github.com/org/repo",
                "feature-1",
                "main",
                "PR title",
                "PR body",
            )
            assert url == "https://github.com/org/repo/pull/1"

    async def test_headers_include_token(self) -> None:
        provider = self._make_provider()
        headers = provider._headers()
        assert headers["Authorization"] == "Bearer test-token"
        assert "github" in headers["Accept"]
