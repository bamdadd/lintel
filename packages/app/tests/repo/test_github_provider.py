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
            await provider.clone_repo("https://github.com/org/repo", "main", "/tmp/dest")
            mock_git.assert_awaited_once_with(
                "clone",
                "--branch",
                "main",
                "--depth",
                "1",
                "https://x-access-token:test-token@github.com/org/repo",
                "/tmp/dest",
            )

    async def test_create_branch_calls_api(self) -> None:
        provider = self._make_provider()
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.create_branch("https://github.com/org/repo", "feature-1", "abc123")
            mock_client.post.assert_awaited_once()

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
        mock_response.status_code = 200
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

    async def test_add_comment_sends_post(self) -> None:
        provider = self._make_provider()
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.add_comment("https://github.com/org/repo", 42, "nice work")
            mock_client.post.assert_awaited_once()
            call_kwargs = mock_client.post.call_args
            assert "/issues/42/comments" in call_kwargs.args[0]

    async def test_list_branches(self) -> None:
        provider = self._make_provider()
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.json.return_value = [{"name": "main"}, {"name": "dev"}]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            branches = await provider.list_branches("https://github.com/org/repo")
            assert branches == ["main", "dev"]

    async def test_get_file_content(self) -> None:
        provider = self._make_provider()
        import base64
        from unittest.mock import MagicMock

        encoded = base64.b64encode(b"hello world").decode()
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": encoded}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            content = await provider.get_file_content(
                "https://github.com/org/repo", "README.md", "main"
            )
            assert content == "hello world"

    async def test_list_commits(self) -> None:
        provider = self._make_provider()
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "sha": "abc123",
                "commit": {
                    "message": "initial",
                    "author": {"name": "dev", "date": "2025-01-01T00:00:00Z"},
                },
            }
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            commits = await provider.list_commits("https://github.com/org/repo", "main", limit=5)
            assert len(commits) == 1
            assert commits[0]["sha"] == "abc123"
            assert commits[0]["message"] == "initial"

    async def test_parse_owner_repo(self) -> None:
        provider = self._make_provider()
        assert provider._parse_owner_repo("https://github.com/org/repo") == ("org", "repo")
        assert provider._parse_owner_repo("https://github.com/org/repo.git") == ("org", "repo")

    async def test_inject_token(self) -> None:
        provider = self._make_provider()
        result = provider._inject_token("https://github.com/org/repo")
        assert result == "https://x-access-token:test-token@github.com/org/repo"

    async def test_inject_token_no_token(self) -> None:
        provider = GitHubRepoProvider(token="")
        result = provider._inject_token("https://github.com/org/repo")
        assert result == "https://github.com/org/repo"

    async def test_headers_include_token(self) -> None:
        provider = self._make_provider()
        headers = provider._headers()
        assert headers["Authorization"] == "Bearer test-token"
        assert "github" in headers["Accept"]
