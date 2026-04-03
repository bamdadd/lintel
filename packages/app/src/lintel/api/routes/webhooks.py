"""Git and CI/CD webhook endpoints — GitHub, GitLab, and generic payload ingestion."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import hmac
import os
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
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
from lintel.domain.types import DeploymentEvent, DeploymentStatus

router = APIRouter()
_logger = structlog.get_logger("lintel.webhooks")

_git_event_listener_provider: StoreProvider[GitEventListener] = StoreProvider()

_WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "test-secret")


# ---------------------------------------------------------------------------
# In-memory deployment store (tracks received CI/CD events)
# ---------------------------------------------------------------------------


class DeploymentStore:
    """In-memory store for received deployment events."""

    def __init__(self) -> None:
        self._events: list[DeploymentEvent] = []

    def add(self, event: DeploymentEvent) -> None:
        self._events.append(event)

    def list_all(self) -> list[DeploymentEvent]:
        return list(self._events)


_deployment_store_provider: StoreProvider[DeploymentStore] = StoreProvider()


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


def _parse_github_workflow_run(body: dict[str, Any]) -> DeploymentEvent:
    repo = body.get("repository", {})
    run = body.get("workflow_run", {})
    action = body.get("action", "")
    conclusion = run.get("conclusion") or ""
    if action == "completed":
        status = DeploymentStatus.SUCCEEDED if conclusion == "success" else DeploymentStatus.FAILED
    else:
        status = DeploymentStatus.STARTED
    return DeploymentEvent(
        deployment_id=str(run.get("id", uuid4().hex)),
        repo_name=repo.get("full_name", ""),
        repo_url=repo.get("html_url", ""),
        status=status,
        workflow_name=run.get("name", ""),
        branch=run.get("head_branch", ""),
        commit_sha=run.get("head_sha", ""),
        sender=body.get("sender", {}).get("login", ""),
        provider="github",
        started_at=run.get("run_started_at", ""),
        finished_at=run.get("updated_at", ""),
        url=run.get("html_url", ""),
    )


@router.post("/webhooks/github")
async def github_webhook(request: Request) -> dict[str, Any]:
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    _verify_github_signature(payload, signature)

    event_type = request.headers.get("X-GitHub-Event", "")
    body: dict[str, Any] = await request.json()

    if event_type == "workflow_run":
        deployment = _parse_github_workflow_run(body)
        store = _deployment_store_provider.get()
        store.add(deployment)
        _logger.info("webhook.github.deployment", deployment_id=deployment.deployment_id)
        return {
            "status": "ok",
            "event_type": event_type,
            "deployment": asdict(deployment),
        }

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


def _parse_gitlab_pipeline(body: dict[str, Any]) -> DeploymentEvent:
    project = body.get("project", {})
    attrs = body.get("object_attributes", {})
    status_str = attrs.get("status", "")
    if status_str == "success":
        status = DeploymentStatus.SUCCEEDED
    elif status_str in ("failed", "canceled"):
        status = DeploymentStatus.FAILED
    else:
        status = DeploymentStatus.STARTED
    return DeploymentEvent(
        deployment_id=str(attrs.get("id", uuid4().hex)),
        repo_name=project.get("path_with_namespace", ""),
        repo_url=project.get("web_url", ""),
        status=status,
        workflow_name="pipeline",
        branch=attrs.get("ref", ""),
        commit_sha=attrs.get("sha", ""),
        sender=body.get("user", {}).get("username", ""),
        provider="gitlab",
        started_at=attrs.get("created_at", ""),
        finished_at=attrs.get("finished_at", ""),
        url=f"{project.get('web_url', '')}/-/pipelines/{attrs.get('id', '')}",
    )


@router.post("/webhooks/gitlab")
async def gitlab_webhook(request: Request) -> dict[str, Any]:
    _verify_gitlab_token(request)
    body: dict[str, Any] = await request.json()
    event_type = body.get("object_kind", "")

    if event_type == "pipeline":
        deployment = _parse_gitlab_pipeline(body)
        store = _deployment_store_provider.get()
        store.add(deployment)
        _logger.info("webhook.gitlab.deployment", deployment_id=deployment.deployment_id)
        return {
            "status": "ok",
            "event_type": event_type,
            "deployment": asdict(deployment),
        }

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


# ---------------------------------------------------------------------------
# Generic CI/CD
# ---------------------------------------------------------------------------


class GenericCICDPayload(BaseModel):
    deployment_id: str
    repo_name: str
    repo_url: str = ""
    status: str = "started"
    workflow_name: str = ""
    branch: str = ""
    commit_sha: str = ""
    sender: str = ""
    provider: str = "generic"
    started_at: str = ""
    finished_at: str = ""
    url: str = ""


_STATUS_MAP: dict[str, DeploymentStatus] = {
    "started": DeploymentStatus.STARTED,
    "succeeded": DeploymentStatus.SUCCEEDED,
    "success": DeploymentStatus.SUCCEEDED,
    "failed": DeploymentStatus.FAILED,
    "failure": DeploymentStatus.FAILED,
}


def _verify_generic_secret(request: Request) -> None:
    token = request.headers.get("X-Webhook-Secret")
    if not token:
        raise HTTPException(status_code=403, detail="Missing X-Webhook-Secret")
    if not hmac.compare_digest(token, _WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid secret")


@router.post("/webhooks/ci-cd")
async def generic_cicd_webhook(request: Request) -> dict[str, Any]:
    _verify_generic_secret(request)
    body = await request.json()
    payload = GenericCICDPayload(**body)
    deployment = DeploymentEvent(
        deployment_id=payload.deployment_id,
        repo_name=payload.repo_name,
        repo_url=payload.repo_url,
        status=_STATUS_MAP.get(payload.status, DeploymentStatus.STARTED),
        workflow_name=payload.workflow_name,
        branch=payload.branch,
        commit_sha=payload.commit_sha,
        sender=payload.sender,
        provider=payload.provider,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        url=payload.url,
    )
    store = _deployment_store_provider.get()
    store.add(deployment)
    _logger.info("webhook.generic.deployment", deployment_id=deployment.deployment_id)
    return {
        "status": "ok",
        "event_type": "ci-cd",
        "deployment": asdict(deployment),
    }


# ---------------------------------------------------------------------------
# Deployments list
# ---------------------------------------------------------------------------


@router.get("/deployments")
async def list_deployments() -> list[dict[str, Any]]:
    store = _deployment_store_provider.get()
    return [asdict(e) for e in store.list_all()]
