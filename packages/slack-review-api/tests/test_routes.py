"""Tests for slack review API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestTriggerReview:
    def test_trigger_with_pr_number(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack/review",
            json={
                "repo_url": "https://github.com/org/repo",
                "pr_number": 42,
                "slack_channel_id": "C123",
                "slack_thread_ts": "1234.5678",
                "slack_user_id": "U999",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["pr_number"] == 42
        assert data["status"] == "completed"

    def test_trigger_parse_from_message(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack/review",
            json={
                "repo_url": "https://github.com/org/repo",
                "slack_channel_id": "C123",
                "slack_thread_ts": "1234.5678",
                "slack_user_id": "U999",
                "message_text": "@lintel review PR #55",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["pr_number"] == 55

    def test_trigger_no_pr_number(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack/review",
            json={
                "repo_url": "https://github.com/org/repo",
                "slack_channel_id": "C123",
                "slack_thread_ts": "1234.5678",
                "slack_user_id": "U999",
                "message_text": "hello world",
            },
        )
        assert resp.status_code == 422


class TestListReviews:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack/reviews")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_create(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack/review",
            json={
                "repo_url": "https://github.com/org/repo",
                "pr_number": 1,
                "slack_channel_id": "C123",
                "slack_thread_ts": "1234.5678",
                "slack_user_id": "U999",
            },
        )
        resp = client.get("/api/v1/slack/reviews")
        assert len(resp.json()) == 1


class TestGetReview:
    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack/reviews/nonexistent")
        assert resp.status_code == 404
