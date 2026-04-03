"""Git event domain types and listener for commit/PR workflows (REQ-026).

Defines domain types for GitHub webhook payloads and a listener that
maps incoming git events to workflow triggers via the event bus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from lintel.contracts.events import EventEnvelope, register_events

if TYPE_CHECKING:
    from lintel.contracts.protocols import CommandDispatcher
    from lintel.domain.reviews.pr_review_service import PRReviewService

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GitEventAction(StrEnum):
    """Actions that can occur on a git event."""

    OPENED = "opened"
    CLOSED = "closed"
    MERGED = "merged"
    SYNCHRONIZE = "synchronize"
    SUBMITTED = "submitted"
    DISMISSED = "dismissed"
    PUSHED = "pushed"


class PRReviewState(StrEnum):
    """Review verdict on a pull request."""

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"
    DISMISSED = "dismissed"


# ---------------------------------------------------------------------------
# Domain types — webhook payloads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GitEvent:
    """Base type for all git-provider events."""

    event_id: str = field(default_factory=lambda: uuid4().hex)
    repo_url: str = ""
    repo_name: str = ""
    sender: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class CommitPushEvent(GitEvent):
    """A push containing one or more commits."""

    branch: str = ""
    before_sha: str = ""
    after_sha: str = ""
    commits: tuple[CommitInfo, ...] = ()


@dataclass(frozen=True)
class CommitInfo:
    """Summary of a single commit within a push event."""

    sha: str = ""
    message: str = ""
    author: str = ""
    added: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()


@dataclass(frozen=True)
class PullRequestEvent(GitEvent):
    """A pull request lifecycle event (opened, closed, merged, synchronize)."""

    action: GitEventAction = GitEventAction.OPENED
    pr_number: int = 0
    pr_title: str = ""
    pr_body: str = ""
    source_branch: str = ""
    target_branch: str = ""
    pr_url: str = ""


@dataclass(frozen=True)
class PRReviewEvent(GitEvent):
    """A review submitted on a pull request."""

    action: GitEventAction = GitEventAction.SUBMITTED
    pr_number: int = 0
    review_state: PRReviewState = PRReviewState.COMMENTED
    review_body: str = ""
    reviewer: str = ""
    pr_url: str = ""


# ---------------------------------------------------------------------------
# Domain events (event-sourced)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GitCommitPushReceived(EventEnvelope):
    """Recorded when a commit push webhook is received."""

    event_type: str = "GitCommitPushReceived"


@dataclass(frozen=True)
class GitPullRequestReceived(EventEnvelope):
    """Recorded when a pull request webhook is received."""

    event_type: str = "GitPullRequestReceived"


@dataclass(frozen=True)
class GitPRReviewReceived(EventEnvelope):
    """Recorded when a PR review webhook is received."""

    event_type: str = "GitPRReviewReceived"


@dataclass(frozen=True)
class GitEventWorkflowTriggered(EventEnvelope):
    """Recorded when a git event triggers a workflow."""

    event_type: str = "GitEventWorkflowTriggered"


@dataclass(frozen=True)
class PRAutoReviewStarted(EventEnvelope):
    """Recorded when an automated PR review begins."""

    event_type: str = "PRAutoReviewStarted"


@dataclass(frozen=True)
class PRAutoReviewCompleted(EventEnvelope):
    """Recorded when an automated PR review finishes."""

    event_type: str = "PRAutoReviewCompleted"


register_events(
    GitCommitPushReceived,
    GitPullRequestReceived,
    GitPRReviewReceived,
    GitEventWorkflowTriggered,
    PRAutoReviewStarted,
    PRAutoReviewCompleted,
)


# ---------------------------------------------------------------------------
# Listener
# ---------------------------------------------------------------------------


class GitEventListener:
    """Maps incoming git events to workflow triggers.

    The listener inspects each git event and, based on configured rules,
    dispatches a ``StartWorkflow`` command to kick off the appropriate
    pipeline (e.g. code-review for new PRs, CI for pushes).
    """

    def __init__(
        self,
        dispatcher: CommandDispatcher,
        *,
        rules: dict[str, str] | None = None,
        auto_review: PRReviewService | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        # rule_key -> workflow_type, e.g. {"pr_opened": "code-review"}
        self._rules: dict[str, str] = rules or {}
        self._auto_review = auto_review

    # -- public API --

    async def on_commit_push(self, event: CommitPushEvent) -> str | None:
        """Handle an incoming commit push event."""
        rule_key = "commit_push"
        workflow_type = self._rules.get(rule_key)
        if workflow_type is None:
            return None
        return await self._trigger(
            workflow_type=workflow_type,
            trigger_source="git:push",
            resource_id=event.after_sha or event.event_id,
            extra={
                "repo_url": event.repo_url,
                "branch": event.branch,
                "commit_count": len(event.commits),
            },
        )

    async def on_pull_request(self, event: PullRequestEvent) -> str | None:
        """Handle an incoming pull request event."""
        # Trigger auto-review on opened/synchronize if configured
        if self._auto_review and event.action in (
            GitEventAction.OPENED,
            GitEventAction.SYNCHRONIZE,
        ):
            try:
                await self._auto_review.review_pr(
                    event.repo_url,
                    event.pr_number,
                )
            except Exception:
                logger.warning(
                    "auto_review_failed",
                    pr_number=event.pr_number,
                    repo_url=event.repo_url,
                    exc_info=True,
                )

        rule_key = f"pr_{event.action.value}"
        workflow_type = self._rules.get(rule_key)
        if workflow_type is None:
            return None
        return await self._trigger(
            workflow_type=workflow_type,
            trigger_source=f"git:pr:{event.action.value}",
            resource_id=str(event.pr_number) or event.event_id,
            extra={
                "repo_url": event.repo_url,
                "pr_number": event.pr_number,
                "pr_title": event.pr_title,
                "source_branch": event.source_branch,
                "target_branch": event.target_branch,
            },
        )

    async def on_pr_review(self, event: PRReviewEvent) -> str | None:
        """Handle an incoming PR review event."""
        rule_key = f"review_{event.review_state.value}"
        workflow_type = self._rules.get(rule_key)
        if workflow_type is None:
            return None
        return await self._trigger(
            workflow_type=workflow_type,
            trigger_source=f"git:review:{event.review_state.value}",
            resource_id=str(event.pr_number) or event.event_id,
            extra={
                "repo_url": event.repo_url,
                "pr_number": event.pr_number,
                "reviewer": event.reviewer,
                "review_state": event.review_state.value,
            },
        )

    # -- internal --

    async def _trigger(
        self,
        *,
        workflow_type: str,
        trigger_source: str,
        resource_id: str,
        extra: dict[str, Any],
    ) -> str:
        from lintel.contracts.types import ThreadRef
        from lintel.workflows.commands import StartWorkflow

        run_ref = f"git:{uuid4().hex[:8]}"
        command = StartWorkflow(
            thread_ref=ThreadRef(
                workspace_id="system",
                channel_id=trigger_source,
                thread_ts=run_ref,
            ),
            workflow_type=workflow_type,
        )
        result = await self._dispatcher.dispatch(command)
        return str(result)
