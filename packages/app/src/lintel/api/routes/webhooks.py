"""Git webhook endpoints — GitHub and GitLab payload ingestion."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
import structlog

from lintel.api_support.provider import StoreProvider
from lintel.domain.git_events import (
    CommitInfo,
    CommitPushEvent,
    GitEventAction,
    GitEventListener,
    PRReviewEvent,
    PRReviewState,
    PullRequestEvent,
)

router = APIRouter()
_logger = structlog.get_logger("lintel.webhooks")

_git_event_listener_provider: StoreProvider[GitEventListener] = StoreProvider()

_WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "test-secret")


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

_GITHUB_ACTION_MAP: dict[str, GitEventAction] = {
    "opened": GitEventAction.OPENED,
    "closed": GitEventAction.CLOSED,
    "synchronize": GitEventAction.SYNCHRONIZE,
    "reopened": GitEventAction.OPENED,
}

_GITHUB_REVIEW_STATE_MAP: dict[str, PRReviewState] = {
    "approved": PRReviewState.APPROVED,
    "changes_requested": PRReviewState.CHANGES_REQUESTED,
    "commented": PRReviewState.COMMENTED,
    "dismissed": PRReviewState.DISMISSED,
}


def _verify_github_signature(payload: bytes, signature: str | None) -> None:
    if not signature:
        raise HTTPException(status_code=403, detail="Missing X-Hub-Signature-256")
    expected = hmac.new(_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"sha256={expected}", signature):
        raise HTTPException(status_code=403, detail="Invalid signature")


def _parse_github_push(body: dict[str, Any]) -> CommitPushEvent:
    repo = body.get("repository", {})
    ref = body.get("ref", "")
    branch = ref.removeprefix("refs/heads/")
    commits = tuple(
        CommitInfo(
            sha=c.get("id", ""),
            message=c.get("message", ""),
            author=c.get("author", {}).get("username", ""),
            added=tuple(c.get("added", ())),
            modified=tuple(c.get("modified", ())),
            removed=tuple(c.get("removed", ())),
        )
        for c in body.get("commits", [])
    )
    return CommitPushEvent(
        repo_url=repo.get("html_url", ""),
        repo_name=repo.get("full_name", ""),
        sender=body.get("sender", {}).get("login", ""),
        branch=branch,
        before_sha=body.get("before", ""),
        after_sha=body.get("after", ""),
        commits=commits,
    )


def _parse_github_pr(body: dict[str, Any]) -> PullRequestEvent:
    repo = body.get("repository", {})
    pr = body.get("pull_request", {})
    action_str = body.get("action", "opened")
    action = _GITHUB_ACTION_MAP.get(action_str, GitEventAction.OPENED)
    if action_str == "closed" and pr.get("merged"):
        action = GitEventAction.MERGED
    return PullRequestEvent(
        repo_url=repo.get("html_url", ""),
        repo_name=repo.get("full_name", ""),
        sender=body.get("sender", {}).get("login", ""),
        action=action,
        pr_number=body.get("number", 0),
        pr_title=pr.get("title", ""),
        pr_body=pr.get("body", "") or "",
        source_branch=pr.get("head", {}).get("ref", ""),
        target_branch=pr.get("base", {}).get("ref", ""),
        pr_url=pr.get("html_url", ""),
    )


def _parse_github_review(body: dict[str, Any]) -> PRReviewEvent:
    repo = body.get("repository", {})
    review = body.get("review", {})
    pr = body.get("pull_request", {})
    state_str = review.get("state", "commented")
    return PRReviewEvent(
        repo_url=repo.get("html_url", ""),
        repo_name=repo.get("full_name", ""),
        sender=body.get("sender", {}).get("login", ""),
        pr_number=pr.get("number", 0),
        review_state=_GITHUB_REVIEW_STATE_MAP.get(state_str, PRReviewState.COMMENTED),
        review_body=review.get("body", "") or "",
        reviewer=review.get("user", {}).get("login", ""),
        pr_url=pr.get("html_url", ""),
    )


@router.post("/webhooks/github")
async def github_webhook(request: Request) -> dict[str, Any]:
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    _verify_github_signature(payload, signature)

    event_type = request.headers.get("X-GitHub-Event", "")
    body: dict[str, Any] = await request.json()

    listener: GitEventListener = _git_event_listener_provider.get()

    if event_type == "push":
        event = _parse_github_push(body)
        await listener.on_commit_push(event)
    elif event_type == "pull_request":
        event = _parse_github_pr(body)  # type: ignore[assignment]
        await listener.on_pull_request(event)  # type: ignore[arg-type]
    elif event_type == "pull_request_review":
        event = _parse_github_review(body)  # type: ignore[assignment]
        await listener.on_pr_review(event)  # type: ignore[arg-type]
    else:
        _logger.info("webhook.github.ignored", event_type=event_type)
        return {"status": "ok", "event_type": "ignored"}

    _logger.info("webhook.github.processed", event_type=event_type)
    return {"status": "ok", "event_type": event_type}


# ---------------------------------------------------------------------------
# GitLab
# ---------------------------------------------------------------------------

_GITLAB_MR_ACTION_MAP: dict[str, GitEventAction] = {
    "open": GitEventAction.OPENED,
    "close": GitEventAction.CLOSED,
    "merge": GitEventAction.MERGED,
    "update": GitEventAction.SYNCHRONIZE,
    "reopen": GitEventAction.OPENED,
}


def _verify_gitlab_token(request: Request) -> None:
    token = request.headers.get("X-Gitlab-Token")
    if not token:
        raise HTTPException(status_code=403, detail="Missing X-Gitlab-Token")
    if not hmac.compare_digest(token, _WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid token")


def _parse_gitlab_push(body: dict[str, Any]) -> CommitPushEvent:
    project = body.get("project", {})
    ref = body.get("ref", "")
    branch = ref.removeprefix("refs/heads/")
    commits = tuple(
        CommitInfo(
            sha=c.get("id", ""),
            message=c.get("message", ""),
            author=c.get("author", {}).get("username", ""),
            added=tuple(c.get("added", ())),
            modified=tuple(c.get("modified", ())),
            removed=tuple(c.get("removed", ())),
        )
        for c in body.get("commits", [])
    )
    return CommitPushEvent(
        repo_url=project.get("web_url", ""),
        repo_name=project.get("path_with_namespace", ""),
        sender=body.get("user_username", ""),
        branch=branch,
        before_sha=body.get("before", ""),
        after_sha=body.get("after", ""),
        commits=commits,
    )


def _parse_gitlab_mr(body: dict[str, Any]) -> PullRequestEvent:
    project = body.get("project", {})
    attrs = body.get("object_attributes", {})
    action_str = attrs.get("action", "open")
    return PullRequestEvent(
        repo_url=project.get("web_url", ""),
        repo_name=project.get("path_with_namespace", ""),
        sender=body.get("user", {}).get("username", ""),
        action=_GITLAB_MR_ACTION_MAP.get(action_str, GitEventAction.OPENED),
        pr_number=attrs.get("iid", 0),
        pr_title=attrs.get("title", ""),
        pr_body=attrs.get("description", "") or "",
        source_branch=attrs.get("source_branch", ""),
        target_branch=attrs.get("target_branch", ""),
        pr_url=attrs.get("url", ""),
    )


@router.post("/webhooks/gitlab")
async def gitlab_webhook(request: Request) -> dict[str, Any]:
    _verify_gitlab_token(request)
    body: dict[str, Any] = await request.json()
    event_type = body.get("object_kind", "")

    listener: GitEventListener = _git_event_listener_provider.get()

    if event_type == "push":
        event = _parse_gitlab_push(body)
        await listener.on_commit_push(event)
    elif event_type == "merge_request":
        event = _parse_gitlab_mr(body)  # type: ignore[assignment]
        await listener.on_pull_request(event)  # type: ignore[arg-type]
    else:
        _logger.info("webhook.gitlab.ignored", event_type=event_type)
        return {"status": "ok", "event_type": "ignored"}

    _logger.info("webhook.gitlab.processed", event_type=event_type)
    return {"status": "ok", "event_type": event_type}
