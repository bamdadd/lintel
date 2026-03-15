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

    async def clone_repo(self, repo_url: str, branch: str, target_dir: str) -> None:
        auth_url = self._inject_token(repo_url)
        await self._run_git("clone", "--branch", branch, "--depth", "1", auth_url, target_dir)
        logger.info("repo_cloned", repo_url=repo_url, branch=branch)

    async def create_branch(self, repo_url: str, branch_name: str, base_sha: str) -> None:
        import httpx

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/git/refs"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            )
            resp.raise_for_status()
        logger.info("branch_created", branch=branch_name)

    def _inject_token(self, repo_url: str) -> str:
        if repo_url.startswith("https://") and self._token:
            return repo_url.replace("https://", f"https://x-access-token:{self._token}@")
        return repo_url

    def _parse_owner_repo(self, repo_url: str) -> tuple[str, str]:
        parts = repo_url.rstrip("/").rstrip(".git").split("/")
        return parts[-2], parts[-1]

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
        *,
        draft: bool = False,
    ) -> str:
        import httpx

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/pulls"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={
                    "title": title,
                    "body": body,
                    "head": head,
                    "base": base,
                    "draft": draft,
                },
            )
            if resp.status_code >= 400:
                logger.error(
                    "github_create_pr_failed",
                    status=resp.status_code,
                    body=resp.text[:500],
                    head=head,
                    base=base,
                )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            pr_url: str = data["html_url"]
            logger.info("pr_created", pr_url=pr_url)
            return pr_url

    async def add_comment(self, repo_url: str, pr_number: int, body: str) -> None:
        import httpx

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/issues/{pr_number}/comments"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"body": body},
            )
            resp.raise_for_status()

    async def list_branches(self, repo_url: str) -> list[str]:
        import httpx

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/branches"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return [b["name"] for b in resp.json()]

    async def get_file_content(self, repo_url: str, path: str, ref: str = "HEAD") -> str:
        import httpx

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/contents/{path}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers(),
                params={"ref": ref},
            )
            resp.raise_for_status()
            data = resp.json()
            import base64

            content: str = base64.b64decode(data["content"]).decode()
            return content

    async def list_commits(
        self, repo_url: str, branch: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        import httpx

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/commits"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers(),
                params={"sha": branch, "per_page": limit},
            )
            resp.raise_for_status()
            return [
                {
                    "sha": c["sha"],
                    "message": c["commit"]["message"],
                    "author": c["commit"]["author"]["name"],
                    "date": c["commit"]["author"]["date"],
                }
                for c in resp.json()
            ]

    async def list_pull_requests(
        self, repo_url: str, state: str = "open", limit: int = 20
    ) -> list[dict[str, Any]]:
        import httpx

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/pulls"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers(),
                params={"state": state, "per_page": limit, "sort": "updated", "direction": "desc"},
            )
            resp.raise_for_status()
            return [
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "state": pr["state"],
                    "author": pr["user"]["login"],
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                    "html_url": pr["html_url"],
                    "head_branch": pr["head"]["ref"],
                    "base_branch": pr["base"]["ref"],
                }
                for pr in resp.json()
            ]
