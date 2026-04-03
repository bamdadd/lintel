"""GitLab implementation of the RepoProvider protocol."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import structlog

logger = structlog.get_logger()


class GitLabRepoProvider:
    """Implements RepoProvider using git CLI and GitLab API via httpx."""

    def __init__(self, token: str, api_base: str = "https://gitlab.com/api/v4") -> None:
        self._token = token
        self._api_base = api_base

    def _headers(self) -> dict[str, str]:
        return {
            "PRIVATE-TOKEN": self._token,
            "Content-Type": "application/json",
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

    def _inject_token(self, repo_url: str) -> str:
        if repo_url.startswith("https://") and self._token:
            return repo_url.replace("https://", f"https://oauth2:{self._token}@")
        return repo_url

    def _parse_project_path(self, repo_url: str) -> str:
        """Extract URL-encoded project path from a GitLab repo URL.

        E.g. ``https://gitlab.com/group/subgroup/repo`` -> ``group%2Fsubgroup%2Frepo``.
        """
        from urllib.parse import quote

        stripped = repo_url.rstrip("/")
        if stripped.endswith(".git"):
            stripped = stripped[: -len(".git")]
        # Remove protocol + host
        path = stripped.split("//", 1)[-1]
        # Remove host portion
        path = "/".join(path.split("/")[1:])
        return quote(path, safe="")

    async def clone_repo(self, repo_url: str, branch: str, target_dir: str) -> None:
        auth_url = self._inject_token(repo_url)
        await self._run_git("clone", "--branch", branch, "--depth", "1", auth_url, target_dir)
        logger.info("repo_cloned", repo_url=repo_url, branch=branch)

    async def create_branch(self, repo_url: str, branch_name: str, base_sha: str) -> None:
        import httpx

        project = self._parse_project_path(repo_url)
        url = f"{self._api_base}/projects/{project}/repository/branches"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"branch": branch_name, "ref": base_sha},
            )
            resp.raise_for_status()
        logger.info("branch_created", branch=branch_name)

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
        """Create a merge request (GitLab equivalent of a PR)."""
        import httpx

        from lintel.repos.types import (
            PrAlreadyExistsError,
            PrAuthError,
            PrCreationError,
            PrTransientError,
        )

        project = self._parse_project_path(repo_url)
        url = f"{self._api_base}/projects/{project}/merge_requests"

        payload: dict[str, Any] = {
            "source_branch": head,
            "target_branch": base,
            "title": f"Draft: {title}" if draft else title,
            "description": body,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json=payload,
                )
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as exc:
            msg = f"Network error creating MR: {exc}"
            logger.error("gitlab_create_mr_network_error", error=str(exc)[:200])
            raise PrTransientError(msg) from exc

        resp_text = resp.text[:500]

        if resp.status_code >= 400:
            logger.error(
                "gitlab_create_mr_failed",
                status=resp.status_code,
                body=resp_text,
                head=head,
                base=base,
            )
            if resp.status_code in (401, 403):
                raise PrAuthError(
                    f"GitLab authentication failed ({resp.status_code}): {resp_text}",
                    status_code=resp.status_code,
                    response_body=resp_text,
                )
            if resp.status_code == 409 or (
                resp.status_code == 422 and "already exists" in resp_text.lower()
            ):
                raise PrAlreadyExistsError(
                    f"A merge request already exists for {head} -> {base}",
                    status_code=resp.status_code,
                    response_body=resp_text,
                )
            if resp.status_code in (429, 500, 502, 503, 504):
                raise PrTransientError(
                    f"GitLab API error ({resp.status_code}): {resp_text}",
                    status_code=resp.status_code,
                    response_body=resp_text,
                )
            raise PrCreationError(
                f"GitLab MR creation failed ({resp.status_code}): {resp_text}",
                status_code=resp.status_code,
                response_body=resp_text,
            )

        data: dict[str, Any] = resp.json()
        mr_url: str = data["web_url"]
        logger.info("mr_created", mr_url=mr_url)
        return mr_url

    async def find_existing_pr(
        self,
        repo_url: str,
        head: str,
        base: str,
    ) -> str:
        """Find an open MR for the given source→target and return its URL, or empty string."""
        prs = await self.list_pull_requests(repo_url, state="open")
        for pr in prs:
            if pr.get("head_branch") == head and pr.get("base_branch") == base:
                return str(pr.get("html_url", ""))
        return ""

    async def add_comment(self, repo_url: str, pr_number: int, body: str) -> None:
        import httpx

        project = self._parse_project_path(repo_url)
        url = f"{self._api_base}/projects/{project}/merge_requests/{pr_number}/notes"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"body": body},
            )
            resp.raise_for_status()

    async def list_branches(self, repo_url: str) -> list[str]:
        import httpx

        project = self._parse_project_path(repo_url)
        url = f"{self._api_base}/projects/{project}/repository/branches"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return [b["name"] for b in resp.json()]

    async def get_file_content(self, repo_url: str, path: str, ref: str = "HEAD") -> str:
        from urllib.parse import quote

        import httpx

        project = self._parse_project_path(repo_url)
        encoded_path = quote(path, safe="")
        url = f"{self._api_base}/projects/{project}/repository/files/{encoded_path}/raw"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers(),
                params={"ref": ref},
            )
            resp.raise_for_status()
            return resp.text

    async def list_commits(
        self, repo_url: str, branch: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        import httpx

        project = self._parse_project_path(repo_url)
        url = f"{self._api_base}/projects/{project}/repository/commits"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers(),
                params={"ref_name": branch, "per_page": limit},
            )
            resp.raise_for_status()
            return [
                {
                    "sha": c["id"],
                    "message": c["message"],
                    "author": c["author_name"],
                    "date": c["created_at"],
                }
                for c in resp.json()
            ]

    async def list_pull_requests(
        self, repo_url: str, state: str = "open", limit: int = 20
    ) -> list[dict[str, Any]]:
        """List merge requests (GitLab equivalent of PRs)."""
        import httpx

        project = self._parse_project_path(repo_url)
        url = f"{self._api_base}/projects/{project}/merge_requests"

        gl_state = {"open": "opened", "closed": "closed", "all": "all"}.get(state, state)

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers(),
                params={
                    "state": gl_state,
                    "per_page": limit,
                    "order_by": "updated_at",
                    "sort": "desc",
                },
            )
            resp.raise_for_status()
            return [
                {
                    "number": mr["iid"],
                    "title": mr["title"],
                    "state": mr["state"],
                    "author": mr["author"]["username"],
                    "created_at": mr["created_at"],
                    "updated_at": mr["updated_at"],
                    "html_url": mr["web_url"],
                    "head_branch": mr["source_branch"],
                    "base_branch": mr["target_branch"],
                }
                for mr in resp.json()
            ]
