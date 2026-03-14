"""Tests for GitHubRepoProvider with mocked subprocess and httpx."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lintel.repos.github_provider import GitHubRepoProvider


class TestTokenInjection:
    def test_inject_token_https(self) -> None:
        provider = GitHubRepoProvider("my-token")
        result = provider._inject_token("https://github.com/org/repo.git")
        assert result == "https://x-access-token:my-token@github.com/org/repo.git"

    def test_inject_token_no_token(self) -> None:
        provider = GitHubRepoProvider("")
        result = provider._inject_token("https://github.com/org/repo.git")
        assert result == "https://github.com/org/repo.git"

    def test_inject_token_ssh_unchanged(self) -> None:
        provider = GitHubRepoProvider("tok")
        result = provider._inject_token("git@github.com:org/repo.git")
        assert result == "git@github.com:org/repo.git"


class TestParseOwnerRepo:
    def test_https_url(self) -> None:
        provider = GitHubRepoProvider("tok")
        owner, repo = provider._parse_owner_repo("https://github.com/myorg/myrepo")
        assert owner == "myorg"
        assert repo == "myrepo"

    def test_https_url_with_git_suffix(self) -> None:
        provider = GitHubRepoProvider("tok")
        owner, repo = provider._parse_owner_repo("https://github.com/myorg/myrepo.git")
        assert owner == "myorg"
        assert repo == "myrepo"

    def test_trailing_slash(self) -> None:
        provider = GitHubRepoProvider("tok")
        owner, repo = provider._parse_owner_repo("https://github.com/org/repo/")
        assert owner == "org"
        assert repo == "repo"


class TestHeaders:
    def test_includes_bearer_token(self) -> None:
        provider = GitHubRepoProvider("ghp_abc123")
        headers = provider._headers()
        assert headers["Authorization"] == "Bearer ghp_abc123"
        assert "application/vnd.github+json" in headers["Accept"]


class TestRunGit:
    async def test_success(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.communicate.return_value = (b"output\n", b"")
            proc.returncode = 0
            mock_exec.return_value = proc
            result = await provider._run_git("status")
            assert result == "output"

    async def test_failure_raises(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.communicate.return_value = (b"", b"error msg")
            proc.returncode = 1
            mock_exec.return_value = proc
            with pytest.raises(RuntimeError, match="error msg"):
                await provider._run_git("checkout", "branch")


class TestCloneRepo:
    async def test_clone_injects_token(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch.object(provider, "_run_git", new_callable=AsyncMock) as mock_git:
            await provider.clone_repo("https://github.com/org/repo", "main", "/tmp/target")
            mock_git.assert_called_once()
            call_str = str(mock_git.call_args)
            assert "clone" in call_str
            assert "x-access-token:tok@" in call_str


class TestCommitAndPush:
    async def test_commit_and_push(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch.object(provider, "_run_git", new_callable=AsyncMock) as mock_git:
            mock_git.return_value = "abc123"
            sha = await provider.commit_and_push("/work", "msg", "feat-branch")
            assert sha == "abc123"
            assert mock_git.call_count == 4  # add, commit, rev-parse, push


class TestCreatePR:
    async def test_create_pr(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"html_url": "https://github.com/org/repo/pull/42"}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp
            url = await provider.create_pr(
                "https://github.com/org/repo", "feat", "main", "title", "body"
            )
            assert url == "https://github.com/org/repo/pull/42"


class TestAddComment:
    async def test_add_comment(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp
            await provider.add_comment("https://github.com/org/repo", 42, "LGTM")
            mock_client.post.assert_called_once()


class TestListBranches:
    async def test_list_branches(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = [{"name": "main"}, {"name": "dev"}]
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp
            branches = await provider.list_branches("https://github.com/org/repo")
            assert branches == ["main", "dev"]


class TestGetFileContent:
    async def test_get_file_content(self) -> None:
        import base64

        provider = GitHubRepoProvider("tok")
        content_b64 = base64.b64encode(b"hello world").decode()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"content": content_b64}
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp
            content = await provider.get_file_content("https://github.com/o/r", "README.md")
            assert content == "hello world"


class TestListCommits:
    async def test_list_commits(self) -> None:
        provider = GitHubRepoProvider("tok")
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = [
                {
                    "sha": "abc",
                    "commit": {
                        "message": "init",
                        "author": {"name": "dev", "date": "2025-01-01"},
                    },
                }
            ]
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp
            commits = await provider.list_commits("https://github.com/o/r", "main")
            assert len(commits) == 1
            assert commits[0]["sha"] == "abc"
            assert commits[0]["author"] == "dev"
