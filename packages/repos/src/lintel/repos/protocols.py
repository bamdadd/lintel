"""Repository store and provider protocol interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lintel.repos.types import Repository


class RepositoryStore(Protocol):
    """Persistence for registered repositories."""

    async def add(self, repository: Repository) -> None: ...

    async def get(self, repo_id: str) -> Repository | None: ...

    async def get_by_url(self, url: str) -> Repository | None: ...

    async def list_all(self) -> list[Repository]: ...

    async def update(self, repository: Repository) -> None: ...

    async def remove(self, repo_id: str) -> None: ...


class RepoProvider(Protocol):
    """Git and PR operations for a repository host."""

    async def clone_repo(
        self,
        repo_url: str,
        branch: str,
        target_dir: str,
    ) -> None: ...

    async def create_branch(
        self,
        repo_url: str,
        branch_name: str,
        base_sha: str,
    ) -> None: ...

    async def commit_and_push(
        self,
        workdir: str,
        message: str,
        branch: str,
    ) -> str: ...

    async def create_pr(
        self,
        repo_url: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str: ...

    async def add_comment(
        self,
        repo_url: str,
        pr_number: int,
        body: str,
    ) -> None: ...

    async def list_branches(
        self,
        repo_url: str,
    ) -> list[str]: ...

    async def get_file_content(
        self,
        repo_url: str,
        path: str,
        ref: str = "HEAD",
    ) -> str: ...

    async def list_commits(
        self,
        repo_url: str,
        branch: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]: ...

    async def list_pull_requests(
        self,
        repo_url: str,
        state: str = "open",
        limit: int = 20,
    ) -> list[dict[str, Any]]: ...
