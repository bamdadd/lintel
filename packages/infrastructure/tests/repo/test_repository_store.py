"""Tests for the in-memory repository store."""

from __future__ import annotations

import pytest
from lintel.contracts.types import Repository, RepoStatus
from lintel.infrastructure.repos.repository_store import InMemoryRepositoryStore


class TestInMemoryRepositoryStore:
    def _make_repo(self, repo_id: str = "repo-1", **kwargs: object) -> Repository:
        defaults = {
            "repo_id": repo_id,
            "name": "my-repo",
            "url": "https://github.com/org/my-repo",
            "default_branch": "main",
            "owner": "org",
            "provider": "github",
        }
        defaults.update(kwargs)
        return Repository(**defaults)  # type: ignore[arg-type]

    async def test_add_and_get(self) -> None:
        store = InMemoryRepositoryStore()
        repo = self._make_repo()
        await store.add(repo)
        result = await store.get("repo-1")
        assert result == repo

    async def test_get_nonexistent_returns_none(self) -> None:
        store = InMemoryRepositoryStore()
        assert await store.get("nope") is None

    async def test_add_duplicate_raises(self) -> None:
        store = InMemoryRepositoryStore()
        repo = self._make_repo()
        await store.add(repo)
        with pytest.raises(ValueError, match="already exists"):
            await store.add(repo)

    async def test_get_by_url(self) -> None:
        store = InMemoryRepositoryStore()
        repo = self._make_repo()
        await store.add(repo)
        result = await store.get_by_url("https://github.com/org/my-repo")
        assert result == repo

    async def test_get_by_url_not_found(self) -> None:
        store = InMemoryRepositoryStore()
        assert await store.get_by_url("https://github.com/org/nope") is None

    async def test_list_all(self) -> None:
        store = InMemoryRepositoryStore()
        await store.add(self._make_repo("r1"))
        await store.add(self._make_repo("r2"))
        repos = await store.list_all()
        assert len(repos) == 2

    async def test_list_all_empty(self) -> None:
        store = InMemoryRepositoryStore()
        assert await store.list_all() == []

    async def test_update(self) -> None:
        store = InMemoryRepositoryStore()
        repo = self._make_repo()
        await store.add(repo)
        updated = Repository(
            repo_id="repo-1",
            name="renamed",
            url=repo.url,
            default_branch="develop",
            owner="org",
            provider="github",
        )
        await store.update(updated)
        result = await store.get("repo-1")
        assert result is not None
        assert result.name == "renamed"
        assert result.default_branch == "develop"

    async def test_update_nonexistent_raises(self) -> None:
        store = InMemoryRepositoryStore()
        with pytest.raises(KeyError, match="not found"):
            await store.update(self._make_repo("nope"))

    async def test_remove(self) -> None:
        store = InMemoryRepositoryStore()
        await store.add(self._make_repo())
        await store.remove("repo-1")
        assert await store.get("repo-1") is None

    async def test_remove_nonexistent_raises(self) -> None:
        store = InMemoryRepositoryStore()
        with pytest.raises(KeyError, match="not found"):
            await store.remove("nope")

    async def test_status_defaults_to_active(self) -> None:
        repo = self._make_repo()
        assert repo.status == RepoStatus.ACTIVE
