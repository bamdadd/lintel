"""GitHub implementation of the RepoProvider protocol."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import structlog

logger = structlog.get_logger()


class GitHubRepoProvider:
    """Implements RepoProvider using git CLI and GitHub API via httpx."""

    def __init__(self, token: str, api_base: str = "https://api.github.com") -> None:
        self._token = token
        self._api_base = api_base

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _run_git(self, *args: str, cwd: str | None = None) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            msg = f"git {args[0]} failed: {stderr.decode()}"
            raise RuntimeError(msg)
        return stdout.decode().strip()

    async def clone(self, repo_url: str, branch: str, dest: str) -> None:
        await self._run_git("clone", "--branch", branch, "--depth", "1", repo_url, dest)
        logger.info("repo_cloned", repo_url=repo_url, branch=branch)

    async def create_branch(self, repo_url: str, base: str, name: str) -> None:
        await self._run_git("checkout", "-b", name, cwd=base)
        logger.info("branch_created", branch=name)

    async def commit_and_push(self, workdir: str, message: str, branch: str) -> str:
        await self._run_git("add", "-A", cwd=workdir)
        await self._run_git("commit", "-m", message, cwd=workdir)
        sha = await self._run_git("rev-parse", "HEAD", cwd=workdir)
        await self._run_git("push", "origin", branch, cwd=workdir)
        logger.info("commit_pushed", sha=sha, branch=branch)
        return sha

    async def create_pr(
        self,
        repo_url: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str:
        import httpx

        owner_repo = repo_url.rstrip("/").split("/")[-2:]
        url = f"{self._api_base}/repos/{owner_repo[0]}/{owner_repo[1]}/pulls"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"title": title, "body": body, "head": head, "base": base},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            pr_url: str = data["html_url"]
            logger.info("pr_created", pr_url=pr_url)
            return pr_url

    async def add_comment(self, repo_url: str, pr_number: int, body: str) -> None:
        import httpx

        owner_repo = repo_url.rstrip("/").split("/")[-2:]
        url = f"{self._api_base}/repos/{owner_repo[0]}/{owner_repo[1]}/issues/{pr_number}/comments"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"body": body},
            )
            resp.raise_for_status()
