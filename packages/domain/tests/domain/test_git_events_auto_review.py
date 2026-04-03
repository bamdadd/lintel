"""Tests for GitEventListener auto-review integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.domain.git_events import (
    GitEventAction,
    GitEventListener,
    PRAutoReviewCompleted,
    PRAutoReviewStarted,
    PullRequestEvent,
)


class _FakeDispatcher:
    def __init__(self) -> None:
        self.dispatch = AsyncMock(return_value="run-123")


class _FakeAutoReview:
    """Minimal mock for PRReviewService."""

    def __init__(self, *, should_fail: bool = False) -> None:
        if should_fail:
            self.review_pr = AsyncMock(side_effect=RuntimeError("review failed"))
        else:
            self.review_pr = AsyncMock(return_value=None)


class TestAutoReviewIntegration:
    async def test_auto_review_triggered_on_pr_opened(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = _FakeAutoReview()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"pr_opened": "code-review"},
            auto_review=auto_review,  # type: ignore[arg-type]
        )
        event = PullRequestEvent(
            action=GitEventAction.OPENED,
            pr_number=42,
            repo_url="https://github.com/org/repo",
        )
        await listener.on_pull_request(event)
        auto_review.review_pr.assert_awaited_once_with("https://github.com/org/repo", 42)

    async def test_auto_review_triggered_on_synchronize(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = _FakeAutoReview()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={},
            auto_review=auto_review,  # type: ignore[arg-type]
        )
        event = PullRequestEvent(
            action=GitEventAction.SYNCHRONIZE,
            pr_number=10,
            repo_url="https://github.com/org/repo",
        )
        await listener.on_pull_request(event)
        auto_review.review_pr.assert_awaited_once_with("https://github.com/org/repo", 10)

    async def test_auto_review_not_triggered_on_closed(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = _FakeAutoReview()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={},
            auto_review=auto_review,  # type: ignore[arg-type]
        )
        event = PullRequestEvent(
            action=GitEventAction.CLOSED,
            pr_number=42,
            repo_url="https://github.com/org/repo",
        )
        await listener.on_pull_request(event)
        auto_review.review_pr.assert_not_awaited()

    async def test_auto_review_not_triggered_when_not_configured(self) -> None:
        dispatcher = _FakeDispatcher()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"pr_opened": "code-review"},
        )
        event = PullRequestEvent(
            action=GitEventAction.OPENED,
            pr_number=42,
            repo_url="https://github.com/org/repo",
        )
        # Should not raise — auto_review is None
        result = await listener.on_pull_request(event)
        assert result == "run-123"

    async def test_auto_review_failure_does_not_block_workflow(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = _FakeAutoReview(should_fail=True)
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"pr_opened": "code-review"},
            auto_review=auto_review,  # type: ignore[arg-type]
        )
        event = PullRequestEvent(
            action=GitEventAction.OPENED,
            pr_number=42,
            repo_url="https://github.com/org/repo",
        )
        # Should not raise — the error is caught and logged
        result = await listener.on_pull_request(event)
        assert result == "run-123"
        auto_review.review_pr.assert_awaited_once()

    async def test_workflow_still_triggers_after_auto_review(self) -> None:
        dispatcher = _FakeDispatcher()
        auto_review = _FakeAutoReview()
        listener = GitEventListener(
            dispatcher,  # type: ignore[arg-type]
            rules={"pr_opened": "code-review"},
            auto_review=auto_review,  # type: ignore[arg-type]
        )
        event = PullRequestEvent(
            action=GitEventAction.OPENED,
            pr_number=42,
            repo_url="https://github.com/org/repo",
        )
        result = await listener.on_pull_request(event)
        assert result == "run-123"
        dispatcher.dispatch.assert_called_once()


class TestAutoReviewDomainEvents:
    def test_pr_auto_review_started_event_type(self) -> None:
        evt = PRAutoReviewStarted()
        assert evt.event_type == "PRAutoReviewStarted"

    def test_pr_auto_review_completed_event_type(self) -> None:
        evt = PRAutoReviewCompleted()
        assert evt.event_type == "PRAutoReviewCompleted"
