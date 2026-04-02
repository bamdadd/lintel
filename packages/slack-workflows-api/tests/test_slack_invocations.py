"""Tests for Slack workflow invocation API endpoints."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_invocation(
    client: TestClient,
    *,
    slack_channel_id: str = "C123",
    slack_thread_ts: str = "1234567890.123456",
    slack_user_id: str = "U999",
    prompt: str = "implement login page",
    project_id: str = "proj-1",
) -> dict:
    resp = client.post(
        "/api/v1/slack/invocations",
        json={
            "slack_channel_id": slack_channel_id,
            "slack_thread_ts": slack_thread_ts,
            "slack_user_id": slack_user_id,
            "prompt": prompt,
            "project_id": project_id,
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestSlackInvocationAPI:
    def test_create_invocation(self, client: TestClient) -> None:
        data = _create_invocation(client)
        assert data["slack_channel_id"] == "C123"
        assert data["slack_user_id"] == "U999"
        assert data["prompt"] == "implement login page"
        assert data["status"] == "pending"
        assert data["invocation_id"]

    def test_list_invocations(self, client: TestClient) -> None:
        _create_invocation(client, slack_channel_id="C111")
        _create_invocation(client, slack_channel_id="C222")
        resp = client.get("/api/v1/slack/invocations")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_list_invocations_filter_by_channel(self, client: TestClient) -> None:
        _create_invocation(client, slack_channel_id="C-FILTER")
        _create_invocation(client, slack_channel_id="C-OTHER")
        resp = client.get("/api/v1/slack/invocations", params={"channel": "C-FILTER"})
        assert resp.status_code == 200
        items = resp.json()
        assert all(i["slack_channel_id"] == "C-FILTER" for i in items)

    def test_list_invocations_filter_by_status(self, client: TestClient) -> None:
        _create_invocation(client)
        resp = client.get("/api/v1/slack/invocations", params={"status": "pending"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_invocation(self, client: TestClient) -> None:
        created = _create_invocation(client)
        inv_id = created["invocation_id"]
        resp = client.get(f"/api/v1/slack/invocations/{inv_id}")
        assert resp.status_code == 200
        assert resp.json()["invocation_id"] == inv_id

    def test_get_invocation_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack/invocations/nonexistent")
        assert resp.status_code == 404

    def test_create_with_thread_context(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack/invocations",
            json={
                "slack_channel_id": "C123",
                "slack_thread_ts": "123.456",
                "slack_user_id": "U1",
                "prompt": "do stuff",
                "project_id": "p1",
                "thread_context": [{"user": "U1", "text": "hello"}],
                "linked_urls": ["https://github.com/example"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["thread_context"]) == 1
        assert data["linked_urls"] == ["https://github.com/example"]
