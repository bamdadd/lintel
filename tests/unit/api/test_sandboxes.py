"""Tests for the sandbox API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from fastapi.testclient import TestClient

from lintel.api.app import create_app


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


class TestSandboxAPI:
    def test_schedule_sandbox_job(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "123.456",
                "agent_role": "coder",
                "repo_url": "https://github.com/org/repo",
                "base_sha": "abc123",
                "commands": ["pytest", "ruff check"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["repo_url"] == "https://github.com/org/repo"
        assert data["base_sha"] == "abc123"
        assert data["commands"] == ["pytest", "ruff check"]
        assert data["agent_role"] == "coder"
        thread = data["thread_ref"]
        assert thread["workspace_id"] == "ws1"
        assert thread["channel_id"] == "ch1"
        assert thread["thread_ts"] == "123.456"
