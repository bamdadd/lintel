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


class RepoTemplate(StrEnum):
    """Scaffold templates for new repositories."""

    REACT_VITE = "react-vite"
    PYTHON_FASTAPI = "python-fastapi"
    MONOREPO = "monorepo"


@dataclass(frozen=True)
class CreateRepoResult:
    """Result of creating a new GitHub repository."""

    repo_url: str
    default_branch: str
    owner: str
    name: str


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
    project_ids: tuple[str, ...] = ()


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


# --- PR creation error hierarchy ---


class PrCreationError(RuntimeError):
    """Base for PR creation failures with captured response details."""

    def __init__(self, message: str, *, status_code: int = 0, response_body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PrAlreadyExistsError(PrCreationError):
    """A pull request already exists for this head/base combination."""


class PrAuthError(PrCreationError):
    """Authentication or authorization failure (401/403)."""


class PrTransientError(PrCreationError):
    """Transient failure (rate limit, server error, network) — safe to retry."""


# --- PR file diff types ---


@dataclass(frozen=True)
class PRFile:
    """A file changed in a pull request."""

    filename: str
    status: str  # added, removed, modified, renamed
    additions: int = 0
    deletions: int = 0
    patch: str = ""


class ReviewVerdict(StrEnum):
    """Verdict for a PR review submission."""

    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


@dataclass(frozen=True)
class InlineComment:
    """An inline review comment on a specific file and line."""

    path: str
    line: int
    body: str
    side: str = "RIGHT"


class CheckRunConclusion(StrEnum):
    """Conclusion for a GitHub check run."""

    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    ACTION_REQUIRED = "action_required"
