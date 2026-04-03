"""Tests for git event domain types and listener (REQ-026)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.domain.git_events import (
    CommitInfo,
    CommitPushEvent,
    GitCommitPushReceived,
    GitEventAction,
    GitEventListener,
    GitEventWorkflowTriggered,
    GitPRReviewReceived,
    GitPullRequestReceived,
    PRReviewEvent,
    PRReviewState,
    PullRequestEvent,
)

# ---------------------------------------------------------------------------
# Domain type construction
# ---------------------------------------------------------------------------


class TestGitEventTypes:
    def test_commit_push_event_defaults(self) -> None:
        evt = CommitPushEvent()
        assert evt.repo_url == ""
        assert evt.branch == ""
        assert evt.commits == ()
        assert evt.event_id  # auto-generated

    def test_commit_push_event_with_commits(self) -> None:
        commit = CommitInfo(
            sha="abc123",
            message="fix: something",
            author="dev",
            added=("new.py",),
            modified=("old.py",),
            removed=(),
        )
        evt = CommitPushEvent(
            repo_url="https://github.com/org/repo",
            branch="main",
            before_sha="000",
            after_sha="abc123",
            commits=(commit,),
        )
        assert len(evt.commits) == 1
        assert evt.commits[0].sha == "abc123"

    def test_pull_request_event(self) -> None:
        evt = PullRequestEvent(
            action=GitEventAction.OPENED,
            pr_number=42,
            pr_title="Add feature",
            source_branch="feat/x",
            target_branch="main",
            repo_url="https://github.com/org/repo",
        )
        assert evt.action == GitEventAction.OPENED
        assert evt.pr_number == 42

    def test_pr_review_event(self) -> None:
        evt = PRReviewEvent(
            pr_number=42,
            review_state=PRReviewState.APPROVED,
            reviewer="alice",
            repo_url="https://github.com/org/repo",
        )
        assert evt.review_state == PRReviewState.APPROVED
        assert evt.reviewer == "alice"

    def test_events_are_frozen(self) -> None:
        evt = CommitPushEvent(branch="main")
        try:
            evt.branch = "other"  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass


class TestDomainEvents:
    def test_git_commit_push_received(self) -> None:
        evt = GitCommitPushReceived()
        assert evt.event_type == "GitCommitPushReceived"

    def test_git_pull_request_received(self) -> None:
        evt = GitPullRequestReceived()
        assert evt.event_type == "GitPullRequestReceived"

    def test_git_pr_review_received(self) -> None:
        evt = GitPRReviewReceived()
        assert evt.event_type == "GitPRReviewReceived"

    def test_git_event_workflow_triggered(self) -> None:
        evt = GitEventWorkflowTriggered()
        assert evt.event_type == "GitEventWorkflowTriggered"


# ---------------------------------------------------------------------------
# Listener
# ---------------------------------------------------------------------------


class _FakeDispatcher:
    def __init__(self) -> None:
        self.calls: list[Any] = []
        self.dispatch = AsyncMock(return_value="run-123")


class TestGitEventListener:
    async def test_commit_push_triggers_workflow(self) -> None:
        dispatcher = _FakeDispatcher()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"commit_push": "ci-pipeline"},
        )
        result = await listener.on_commit_push(
            CommitPushEvent(
                repo_url="https://github.com/org/repo",
                branch="main",
                after_sha="abc123",
            )
        )
        assert result == "run-123"
        dispatcher.dispatch.assert_called_once()
        cmd = dispatcher.dispatch.call_args[0][0]
        assert cmd.workflow_type == "ci-pipeline"

    async def test_commit_push_no_matching_rule(self) -> None:
        dispatcher = _FakeDispatcher()
        listener = GitEventListener(dispatcher, rules={})  # type: ignore[arg-type]
        result = await listener.on_commit_push(CommitPushEvent())
        assert result is None
        dispatcher.dispatch.assert_not_called()

    async def test_pr_opened_triggers_workflow(self) -> None:
        dispatcher = _FakeDispatcher()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"pr_opened": "code-review"},
        )
        result = await listener.on_pull_request(
            PullRequestEvent(
                action=GitEventAction.OPENED,
                pr_number=42,
                repo_url="https://github.com/org/repo",
            )
        )
        assert result == "run-123"
        cmd = dispatcher.dispatch.call_args[0][0]
        assert cmd.workflow_type == "code-review"

    async def test_pr_merged_triggers_different_workflow(self) -> None:
        dispatcher = _FakeDispatcher()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"pr_merged": "deploy-pipeline"},
        )
        result = await listener.on_pull_request(
            PullRequestEvent(action=GitEventAction.MERGED, pr_number=99)
        )
        assert result == "run-123"
        cmd = dispatcher.dispatch.call_args[0][0]
        assert cmd.workflow_type == "deploy-pipeline"

    async def test_pr_review_approved_triggers(self) -> None:
        dispatcher = _FakeDispatcher()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"review_approved": "merge-pipeline"},
        )
        result = await listener.on_pr_review(
            PRReviewEvent(
                pr_number=42,
                review_state=PRReviewState.APPROVED,
                reviewer="alice",
            )
        )
        assert result == "run-123"
        cmd = dispatcher.dispatch.call_args[0][0]
        assert cmd.workflow_type == "merge-pipeline"

    async def test_pr_review_no_matching_rule(self) -> None:
        dispatcher = _FakeDispatcher()
        listener = GitEventListener(dispatcher, rules={})  # type: ignore[arg-type]
        result = await listener.on_pr_review(PRReviewEvent(review_state=PRReviewState.COMMENTED))
        assert result is None
        dispatcher.dispatch.assert_not_called()


class TestGitEventListenerAutoReview:
    async def test_pr_opened_triggers_auto_review(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = AsyncMock()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={},
            auto_review=auto_review,
        )
        await listener.on_pull_request(
            PullRequestEvent(
                action=GitEventAction.OPENED,
                pr_number=42,
                repo_url="https://github.com/org/repo",
            )
        )
        auto_review.review_pr.assert_awaited_once_with(
            "https://github.com/org/repo", 42
        )

    async def test_pr_synchronize_triggers_auto_review(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = AsyncMock()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={},
            auto_review=auto_review,
        )
        await listener.on_pull_request(
            PullRequestEvent(
                action=GitEventAction.SYNCHRONIZE,
                pr_number=10,
                repo_url="https://github.com/org/repo",
            )
        )
        auto_review.review_pr.assert_awaited_once()

    async def test_pr_closed_does_not_trigger_auto_review(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = AsyncMock()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={},
            auto_review=auto_review,
        )
        await listener.on_pull_request(
            PullRequestEvent(action=GitEventAction.CLOSED, pr_number=5)
        )
        auto_review.review_pr.assert_not_awaited()

    async def test_auto_review_failure_does_not_block_workflow(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = AsyncMock()
        auto_review.review_pr.side_effect = RuntimeError("API error")
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"pr_opened": "code-review"},
            auto_review=auto_review,
        )
        result = await listener.on_pull_request(
            PullRequestEvent(
                action=GitEventAction.OPENED,
                pr_number=42,
                repo_url="https://github.com/org/repo",
            )
        )
        # Workflow should still trigger despite auto-review failure
        assert result == "run-123"
        dispatcher.dispatch.assert_called_once()

    async def test_no_auto_review_when_not_configured(self) -> None:
        dispatcher = _FakeDispatcher()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={},
        )
        # Should not raise — auto_review is None
        await listener.on_pull_request(
            PullRequestEvent(action=GitEventAction.OPENED, pr_number=1)
        )
