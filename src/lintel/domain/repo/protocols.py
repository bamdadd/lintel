"""Repo provider protocol."""

from __future__ import annotations

from typing import Protocol


class RepoProvider(Protocol):
    """Git and PR operations for a repository host."""

    async def clone(self, repo_url: str, branch: str, dest: str) -> None: ...

    async def create_branch(self, repo_url: str, base: str, name: str) -> None: ...

    async def commit_and_push(self, workdir: str, message: str, branch: str) -> str: ...

    async def create_pr(
        self,
        repo_url: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str: ...

    async def add_comment(self, repo_url: str, pr_number: int, body: str) -> None: ...
