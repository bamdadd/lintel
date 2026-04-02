"""Tests for webhook event types."""

from __future__ import annotations

from lintel.repos.types import (
    RepoProviderType,
    WebhookCommit,
    WebhookEvent,
    WebhookEventKind,
)


class TestWebhookEventKind:
    def test_push_value(self) -> None:
        assert WebhookEventKind.PUSH == "push"

    def test_pr_opened_value(self) -> None:
        assert WebhookEventKind.PULL_REQUEST_OPENED == "pull_request_opened"

    def test_pr_merged_value(self) -> None:
        assert WebhookEventKind.PULL_REQUEST_MERGED == "pull_request_merged"


class TestRepoProviderType:
    def test_github(self) -> None:
        assert RepoProviderType.GITHUB == "github"

    def test_gitlab(self) -> None:
        assert RepoProviderType.GITLAB == "gitlab"


class TestWebhookCommit:
    def test_frozen(self) -> None:
        commit = WebhookCommit(sha="abc123", message="fix", author="dev")
        assert commit.sha == "abc123"

    def test_default_timestamp(self) -> None:
        commit = WebhookCommit(sha="a", message="m", author="a")
        assert commit.timestamp == ""


class TestWebhookEvent:
    def test_push_event(self) -> None:
        event = WebhookEvent(
            event_id="evt-1",
            provider=RepoProviderType.GITHUB,
            kind=WebhookEventKind.PUSH,
            repo_url="https://github.com/org/repo",
            branch="main",
            sender="dev",
            commits=(WebhookCommit(sha="abc", message="feat: new", author="dev"),),
        )
        assert event.kind == WebhookEventKind.PUSH
        assert len(event.commits) == 1
        assert event.pr_number is None

    def test_pr_event(self) -> None:
        event = WebhookEvent(
            event_id="evt-2",
            provider=RepoProviderType.GITLAB,
            kind=WebhookEventKind.PULL_REQUEST_OPENED,
            repo_url="https://gitlab.com/group/repo",
            branch="feature-x",
            sender="dev",
            title="Add feature X",
            pr_number=42,
        )
        assert event.pr_number == 42
        assert event.provider == RepoProviderType.GITLAB

    def test_default_raw_payload(self) -> None:
        event = WebhookEvent(
            event_id="e",
            provider=RepoProviderType.GITHUB,
            kind=WebhookEventKind.PUSH,
            repo_url="https://github.com/a/b",
        )
        assert event.raw_payload == {}

    def test_frozen(self) -> None:
        event = WebhookEvent(
            event_id="e",
            provider=RepoProviderType.GITHUB,
            kind=WebhookEventKind.PUSH,
            repo_url="https://github.com/a/b",
        )
        import pytest

        with pytest.raises(AttributeError):
            event.event_id = "other"  # type: ignore[misc]
