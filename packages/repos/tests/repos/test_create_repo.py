"""Tests for GitHubRepoProvider.create_repo with mocked GitHub API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from lintel.repos.github_provider import GitHubRepoProvider
from lintel.repos.types import RepoTemplate


class TestCreateRepo:
    def _make_provider(self) -> GitHubRepoProvider:
        return GitHubRepoProvider(token="test-token", api_base="https://api.github.com")

    def _mock_httpx_client(
        self,
        *,
        status_code: int = 201,
        json_data: dict | None = None,
    ) -> MagicMock:
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {
            "html_url": "https://github.com/myorg/new-repo",
            "default_branch": "main",
            "owner": {"login": "myorg"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    async def test_create_repo_without_template(self) -> None:
        provider = self._make_provider()
        mock_client = self._mock_httpx_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.create_repo("myorg", "new-repo")

        assert result.repo_url == "https://github.com/myorg/new-repo"
        assert result.default_branch == "main"
        assert result.owner == "myorg"
        assert result.name == "new-repo"

        # Should have called the org endpoint
        call_args = mock_client.post.call_args
        assert "/orgs/myorg/repos" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["name"] == "new-repo"
        assert payload["private"] is True
        assert payload["auto_init"] is True  # No template → auto_init

    async def test_create_repo_falls_back_to_user_endpoint(self) -> None:
        provider = self._make_provider()

        # First call returns 404 (not an org), second succeeds
        not_found_resp = MagicMock()
        not_found_resp.status_code = 404

        success_resp = MagicMock()
        success_resp.status_code = 201
        success_resp.json.return_value = {
            "html_url": "https://github.com/myuser/new-repo",
            "default_branch": "main",
            "owner": {"login": "myuser"},
        }
        success_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.side_effect = [not_found_resp, success_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.create_repo("myuser", "new-repo")

        assert result.repo_url == "https://github.com/myuser/new-repo"
        assert mock_client.post.call_count == 2
        # Second call should use /user/repos
        second_call = mock_client.post.call_args_list[1]
        assert "/user/repos" in second_call.args[0]

    async def test_create_repo_with_template(self) -> None:
        provider = self._make_provider()
        mock_client = self._mock_httpx_client()

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch.object(provider, "_run_git", new_callable=AsyncMock) as mock_git,
        ):
            mock_git.return_value = ""
            result = await provider.create_repo(
                "myorg", "new-repo", template=RepoTemplate.REACT_VITE
            )

        assert result.repo_url == "https://github.com/myorg/new-repo"

        # Should have called the org endpoint with auto_init=False
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["auto_init"] is False  # Template provided → no auto_init

        # Verify git commands were called (init, remote add, add, commit, push)
        git_commands = [call.args[0] for call in mock_git.call_args_list]
        assert "init" in git_commands
        assert "remote" in git_commands
        assert "add" in git_commands
        assert "commit" in git_commands
        assert "push" in git_commands

    async def test_create_repo_with_description(self) -> None:
        provider = self._make_provider()
        mock_client = self._mock_httpx_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.create_repo("myorg", "new-repo", description="My cool project")

        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["description"] == "My cool project"

    async def test_create_repo_public(self) -> None:
        provider = self._make_provider()
        mock_client = self._mock_httpx_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.create_repo("myorg", "new-repo", private=False)

        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["private"] is False
