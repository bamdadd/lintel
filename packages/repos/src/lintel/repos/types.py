"""Repository domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class RepoStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    ERROR = "error"


class RepoProviderType(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"


class WebhookEventKind(StrEnum):
    PUSH = "push"
    PULL_REQUEST_OPENED = "pull_request_opened"
    PULL_REQUEST_CLOSED = "pull_request_closed"
    PULL_REQUEST_MERGED = "pull_request_merged"


@dataclass(frozen=True)
class Repository:
    """A registered git repository that workflows can operate on."""

    repo_id: str
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"
    status: RepoStatus = RepoStatus.ACTIVE


@dataclass(frozen=True)
class WebhookCommit:
    """A single commit included in a push webhook payload."""

    sha: str
    message: str
    author: str
    timestamp: str = ""


@dataclass(frozen=True)
class WebhookEvent:
    """Normalised webhook event received from GitHub or GitLab."""

    event_id: str
    provider: RepoProviderType
    kind: WebhookEventKind
    repo_url: str
    ref: str = ""
    branch: str = ""
    sender: str = ""
    title: str = ""
    pr_number: int | None = None
    commits: tuple[WebhookCommit, ...] = ()
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw_payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RepoClassification:
    """Result of classifying a user message to a repository."""

    repo_id: str
    repo_name: str
    confidence: float
    matched_keywords: tuple[str, ...] = ()
    reason: str = ""
