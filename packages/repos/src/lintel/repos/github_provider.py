"""GitHub implementation of the RepoProvider protocol."""

from __future__ import annotations

import asyncio
import subprocess
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.repos.types import (
        CheckRunConclusion,
        CreateRepoResult,
        InlineComment,
        PRFile,
        RepoTemplate,
        ReviewVerdict,
    )

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

    async def create_repo(
        self,
        owner: str,
        name: str,
        *,
        private: bool = True,
        description: str = "",
        template: RepoTemplate | None = None,
    ) -> CreateRepoResult:
        """Create a new GitHub repository and optionally push scaffold template files."""
        import tempfile

        import httpx

        from lintel.repos.types import CreateRepoResult

        # Create the repo via GitHub API
        url = f"{self._api_base}/orgs/{owner}/repos"
        payload: dict[str, Any] = {
            "name": name,
            "private": private,
            "auto_init": template is None,
        }
        if description:
            payload["description"] = description

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            if resp.status_code == 404:
                # Not an org — try user endpoint
                url = f"{self._api_base}/user/repos"
                resp = await client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()

        data: dict[str, Any] = resp.json()
        repo_url: str = data["html_url"]
        default_branch: str = data.get("default_branch", "main")
        actual_owner: str = data.get("owner", {}).get("login", owner)

        logger.info("repo_created", repo_url=repo_url, owner=actual_owner, name=name)

        # Push scaffold template if requested
        if template is not None:
            from lintel.repos.templates import get_template_files

            files = get_template_files(template, name)
            with tempfile.TemporaryDirectory() as tmpdir:
                await self._run_git("init", "-b", default_branch, cwd=tmpdir)
                await self._run_git(
                    "remote", "add", "origin", self._inject_token(repo_url), cwd=tmpdir
                )
                # Write template files
                import os

                for filepath, content in files.items():
                    full_path = os.path.join(tmpdir, filepath)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w") as f:
                        f.write(content)

                await self._run_git("add", "-A", cwd=tmpdir)
                await self._run_git(
                    "commit", "-m", f"chore: bootstrap {template.value} template", cwd=tmpdir
                )
                await self._run_git("push", "-u", "origin", default_branch, cwd=tmpdir)
            logger.info("template_pushed", template=template.value, repo_url=repo_url)

        return CreateRepoResult(
            repo_url=repo_url,
            default_branch=default_branch,
            owner=actual_owner,
            name=name,
        )

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

        from lintel.repos.types import (
            PrAlreadyExistsError,
            PrAuthError,
            PrCreationError,
            PrTransientError,
        )

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/pulls"

        try:
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
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as exc:
            msg = f"Network error creating PR: {exc}"
            logger.error("github_create_pr_network_error", error=str(exc)[:200])
            raise PrTransientError(msg) from exc

        resp_text = resp.text[:500]

        if resp.status_code >= 400:
            logger.error(
                "github_create_pr_failed",
                status=resp.status_code,
                body=resp_text,
                head=head,
                base=base,
            )

            # Classify the error
            if resp.status_code in (401, 403):
                raise PrAuthError(
                    f"GitHub authentication failed ({resp.status_code}): {resp_text}",
                    status_code=resp.status_code,
                    response_body=resp_text,
                )

            if resp.status_code == 422 and "already exists" in resp_text.lower():
                raise PrAlreadyExistsError(
                    f"A pull request already exists for {head} -> {base}",
                    status_code=resp.status_code,
                    response_body=resp_text,
                )

            if resp.status_code in (429, 500, 502, 503, 504):
                raise PrTransientError(
                    f"GitHub API error ({resp.status_code}): {resp_text}",
                    status_code=resp.status_code,
                    response_body=resp_text,
                )

            # Other 4xx errors (validation, etc.)
            raise PrCreationError(
                f"GitHub PR creation failed ({resp.status_code}): {resp_text}",
                status_code=resp.status_code,
                response_body=resp_text,
            )

        data: dict[str, Any] = resp.json()
        pr_url: str = data["html_url"]
        logger.info("pr_created", pr_url=pr_url)
        return pr_url

    async def find_existing_pr(
        self,
        repo_url: str,
        head: str,
        base: str,
    ) -> str:
        """Find an open PR for the given head→base and return its URL, or empty string."""
        prs = await self.list_pull_requests(repo_url, state="open")
        for pr in prs:
            if pr.get("head_branch") == head and pr.get("base_branch") == base:
                return str(pr.get("html_url", ""))
        return ""

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

    async def get_pr_files(
        self,
        repo_url: str,
        pr_number: int,
    ) -> list[PRFile]:
        """Fetch the list of files changed in a pull request."""
        import httpx

        from lintel.repos.types import PRFile

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/pulls/{pr_number}/files"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return [
                PRFile(
                    filename=f["filename"],
                    status=f["status"],
                    additions=f.get("additions", 0),
                    deletions=f.get("deletions", 0),
                    patch=f.get("patch", ""),
                )
                for f in resp.json()
            ]

    async def create_review(
        self,
        repo_url: str,
        pr_number: int,
        body: str,
        verdict: ReviewVerdict,
        comments: list[InlineComment] | None = None,
    ) -> str:
        """Post a pull request review with optional inline comments."""
        import httpx

        from lintel.repos.types import InlineComment, ReviewVerdict

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

        event_str = verdict.value if isinstance(verdict, ReviewVerdict) else str(verdict)
        payload: dict[str, Any] = {"body": body, "event": event_str}
        if comments:
            payload["comments"] = [
                {"path": c.path, "line": c.line, "body": c.body, "side": c.side}
                if isinstance(c, InlineComment)
                else c
                for c in comments
            ]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        logger.info("pr_review_created", pr_number=pr_number, review_event=event_str)
        return str(data["id"])

    async def create_check_run(
        self,
        repo_url: str,
        head_sha: str,
        name: str,
        status: str = "in_progress",
        conclusion: CheckRunConclusion | None = None,
        title: str = "",
        summary: str = "",
    ) -> str:
        """Create a GitHub check run."""
        import httpx

        from lintel.repos.types import CheckRunConclusion

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/check-runs"

        payload: dict[str, Any] = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
        }
        if conclusion is not None:
            payload["conclusion"] = (
                conclusion.value if isinstance(conclusion, CheckRunConclusion) else str(conclusion)
            )
        if title or summary:
            payload["output"] = {"title": title, "summary": summary}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        logger.info("check_run_created", name=name, head_sha=head_sha[:8])
        return str(data["id"])

    async def update_check_run(
        self,
        repo_url: str,
        check_run_id: str,
        status: str = "completed",
        conclusion: CheckRunConclusion | None = None,
        title: str = "",
        summary: str = "",
    ) -> None:
        """Update an existing GitHub check run."""
        import httpx

        from lintel.repos.types import CheckRunConclusion

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/check-runs/{check_run_id}"

        payload: dict[str, Any] = {"status": status}
        if conclusion is not None:
            payload["conclusion"] = (
                conclusion.value if isinstance(conclusion, CheckRunConclusion) else str(conclusion)
            )
        if title or summary:
            payload["output"] = {"title": title, "summary": summary}

        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                url,
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
        logger.info("check_run_updated", check_run_id=check_run_id)

    async def get_pr_diff(self, repo_url: str, pr_number: int) -> str:
        """Fetch the unified diff for a pull request."""
        import httpx

        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{self._api_base}/repos/{owner}/{repo}/pulls/{pr_number}"

        headers = self._headers()
        headers["Accept"] = "application/vnd.github.v3.diff"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
