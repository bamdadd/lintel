"""Tests for SlackReviewHandler and PR number parsing."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from lintel.slack_review_api.handler import SlackReviewHandler, parse_pr_number
from lintel.slack_review_api.store import InMemorySlackReviewStore, SlackReviewRequest


class TestParsePrNumber:
    def test_pr_hash_number(self) -> None:
        assert parse_pr_number("review PR #42") == 42

    def test_pr_no_hash(self) -> None:
        assert parse_pr_number("review PR 99") == 99

    def test_pull_request(self) -> None:
        assert parse_pr_number("review pull request #7") == 7

    def test_case_insensitive(self) -> None:
        assert parse_pr_number("review pr #123") == 123

    def test_no_match(self) -> None:
        assert parse_pr_number("hello world") is None

    def test_embedded_in_sentence(self) -> None:
        assert parse_pr_number("@lintel review PR #55 please") == 55


class TestSlackReviewHandler:
    @pytest.fixture()
    def store(self) -> InMemorySlackReviewStore:
        return InMemorySlackReviewStore()

    @pytest.fixture()
    def github(self) -> AsyncMock:
        gh = AsyncMock()
        gh.get_pr_diff = AsyncMock(
            return_value=(
                "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n+print('hello')\n"
            )
        )
        gh.add_comment = AsyncMock()
        return gh

    @pytest.fixture()
    def handler(self, github: AsyncMock, store: InMemorySlackReviewStore) -> SlackReviewHandler:
        return SlackReviewHandler(github_provider=github, review_store=store)

    async def test_run_review_approve(
        self,
        handler: SlackReviewHandler,
        store: InMemorySlackReviewStore,
    ) -> None:
        review = SlackReviewRequest(
            review_id="r1",
            repo_url="https://github.com/org/repo",
            pr_number=42,
            slack_channel_id="C123",
            slack_thread_ts="1234.5678",
            slack_user_id="U999",
        )
        await store.add(review)
        result = await handler.run_review(review)

        assert result["status"] == "completed"
        assert result["verdict"] == "approve"
        assert result["pr_number"] == 42

    async def test_run_review_empty_diff(
        self,
        handler: SlackReviewHandler,
        github: AsyncMock,
        store: InMemorySlackReviewStore,
    ) -> None:
        github.get_pr_diff.return_value = ""
        review = SlackReviewRequest(
            review_id="r2",
            repo_url="https://github.com/org/repo",
            pr_number=10,
            slack_channel_id="C123",
            slack_thread_ts="1234.5678",
            slack_user_id="U999",
        )
        await store.add(review)
        result = await handler.run_review(review)

        assert result["status"] == "completed"
        assert result["verdict"] == "approve"

    async def test_run_review_fetch_failure(
        self,
        handler: SlackReviewHandler,
        github: AsyncMock,
        store: InMemorySlackReviewStore,
    ) -> None:
        github.get_pr_diff.side_effect = RuntimeError("API error")
        review = SlackReviewRequest(
            review_id="r3",
            repo_url="https://github.com/org/repo",
            pr_number=5,
            slack_channel_id="C123",
            slack_thread_ts="1234.5678",
            slack_user_id="U999",
        )
        await store.add(review)
        result = await handler.run_review(review)

        assert result["status"] == "failed"

    async def test_format_slack_message(
        self,
        handler: SlackReviewHandler,
    ) -> None:
        result = {"verdict": "approve", "review_body": "Looks good.", "pr_number": 42}
        msg = handler.format_slack_message(result)
        assert "PR #42" in msg
        assert ":white_check_mark:" in msg
