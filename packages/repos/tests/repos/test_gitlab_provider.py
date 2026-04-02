"""Tests for the GitLab repository provider."""

from __future__ import annotations

from lintel.repos.gitlab_provider import GitLabRepoProvider


class TestGitLabRepoProviderInit:
    def test_default_api_base(self) -> None:
        provider = GitLabRepoProvider(token="glpat-xxx")
        assert provider._api_base == "https://gitlab.com/api/v4"

    def test_custom_api_base(self) -> None:
        provider = GitLabRepoProvider(token="glpat-xxx", api_base="https://gl.corp.com/api/v4")
        assert provider._api_base == "https://gl.corp.com/api/v4"

    def test_headers_contain_private_token(self) -> None:
        provider = GitLabRepoProvider(token="glpat-xxx")
        headers = provider._headers()
        assert headers["PRIVATE-TOKEN"] == "glpat-xxx"


class TestGitLabTokenInjection:
    def test_inject_token_https(self) -> None:
        provider = GitLabRepoProvider(token="glpat-xxx")
        result = provider._inject_token("https://gitlab.com/group/repo.git")
        assert result == "https://oauth2:glpat-xxx@gitlab.com/group/repo.git"

    def test_inject_token_non_https(self) -> None:
        provider = GitLabRepoProvider(token="glpat-xxx")
        result = provider._inject_token("git@gitlab.com:group/repo.git")
        assert result == "git@gitlab.com:group/repo.git"


class TestGitLabProjectPathParsing:
    def test_simple_path(self) -> None:
        provider = GitLabRepoProvider(token="t")
        assert provider._parse_project_path("https://gitlab.com/group/repo") == "group%2Frepo"

    def test_path_with_dot_git(self) -> None:
        provider = GitLabRepoProvider(token="t")
        result = provider._parse_project_path("https://gitlab.com/org/project.git")
        assert result == "org%2Fproject"

    def test_subgroup_path(self) -> None:
        provider = GitLabRepoProvider(token="t")
        result = provider._parse_project_path("https://gitlab.com/group/sub/repo")
        assert result == "group%2Fsub%2Frepo"

    def test_trailing_slash(self) -> None:
        provider = GitLabRepoProvider(token="t")
        result = provider._parse_project_path("https://gitlab.com/group/repo/")
        assert result == "group%2Frepo"


class TestGitLabProviderSatisfiesProtocol:
    """Verify GitLabRepoProvider has the same interface as RepoProvider."""

    def test_has_all_protocol_methods(self) -> None:
        from lintel.repos.protocols import RepoProvider

        protocol_methods = {
            name
            for name in dir(RepoProvider)
            if not name.startswith("_") and callable(getattr(RepoProvider, name, None))
        }
        provider_methods = {
            name
            for name in dir(GitLabRepoProvider)
            if not name.startswith("_") and callable(getattr(GitLabRepoProvider, name, None))
        }
        assert protocol_methods.issubset(provider_methods), (
            f"Missing methods: {protocol_methods - provider_methods}"
        )
