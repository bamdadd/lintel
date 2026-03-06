"""Tests for the PII API endpoints."""

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


class TestPIIAPI:
    def test_reveal_pii(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/pii/reveal",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "123.456",
                "placeholder": "<PII_EMAIL_1>",
                "requester_id": "user42",
                "reason": "customer support",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["placeholder"] == "<PII_EMAIL_1>"
        assert data["requester_id"] == "user42"
        assert data["reason"] == "customer support"
        thread = data["thread_ref"]
        assert thread["workspace_id"] == "ws1"
        assert thread["channel_id"] == "ch1"
        assert thread["thread_ts"] == "123.456"
