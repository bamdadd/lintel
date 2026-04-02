"""Tests for repo auto-classification integration in ChatService."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from lintel.chat_api.service import ChatService
from lintel.repos.types import RepoStatus


@dataclass
class _FakeRepo:
    repo_id: str
    name: str
    url: str
    owner: str = ""
    default_branch: str = "main"
    status: RepoStatus = RepoStatus.ACTIVE


class TestClassifyRepo:
    @pytest.fixture()
    def service(self) -> ChatService:
        request = MagicMock()
        store = AsyncMock()
        return ChatService(request=request, store=store)

    async def test_returns_none_when_no_repo_store(self, service: ChatService) -> None:
        service._request.app.state.repository_store = None
        url, branch = await service._classify_repo("fix the lintel pipeline")
        assert url is None
        assert branch is None

    async def test_returns_none_when_no_active_repos(self, service: ChatService) -> None:
        repo_store = AsyncMock()
        repo_store.list_all.return_value = []
        service._request.app.state.repository_store = repo_store
        url, branch = await service._classify_repo("fix something")
        assert url is None
        assert branch is None

    async def test_classifies_matching_repo(self, service: ChatService) -> None:
        repo = _FakeRepo(
            repo_id="r1",
            name="lintel",
            url="https://github.com/acme/lintel",
            owner="acme",
            default_branch="develop",
        )
        repo_store = AsyncMock()
        repo_store.list_all.return_value = [repo]
        repo_store.get.return_value = repo
        service._request.app.state.repository_store = repo_store

        url, branch = await service._classify_repo("fix the lintel CI")
        assert url == "https://github.com/acme/lintel"
        assert branch == "develop"

    async def test_returns_none_when_low_confidence(self, service: ChatService) -> None:
        repo = _FakeRepo(
            repo_id="r1",
            name="backend-service",
            url="https://github.com/acme/backend-service",
        )
        repo_store = AsyncMock()
        repo_store.list_all.return_value = [repo]
        service._request.app.state.repository_store = repo_store

        url, branch = await service._classify_repo("what is the weather today")
        assert url is None
        assert branch is None

    async def test_picks_best_match_from_multiple_repos(self, service: ChatService) -> None:
        repos = [
            _FakeRepo(repo_id="r1", name="frontend", url="https://github.com/org/frontend"),
            _FakeRepo(repo_id="r2", name="backend", url="https://github.com/org/backend"),
        ]
        repo_store = AsyncMock()
        repo_store.list_all.return_value = repos
        repo_store.get.return_value = repos[1]
        service._request.app.state.repository_store = repo_store

        url, _branch = await service._classify_repo("fix the backend API")
        assert url == "https://github.com/org/backend"

    async def test_skips_inactive_repos(self, service: ChatService) -> None:
        repos = [
            _FakeRepo(
                repo_id="r1",
                name="lintel",
                url="https://github.com/org/lintel",
                status=RepoStatus.ARCHIVED,
            ),
        ]
        repo_store = AsyncMock()
        repo_store.list_all.return_value = repos
        service._request.app.state.repository_store = repo_store

        url, branch = await service._classify_repo("fix lintel")
        assert url is None
        assert branch is None

    async def test_handles_store_exception_gracefully(self, service: ChatService) -> None:
        repo_store = AsyncMock()
        repo_store.list_all.side_effect = RuntimeError("DB down")
        service._request.app.state.repository_store = repo_store

        url, branch = await service._classify_repo("fix lintel")
        assert url is None
        assert branch is None
