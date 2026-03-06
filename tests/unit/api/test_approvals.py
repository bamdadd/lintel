"""Tests for the approval API endpoints."""

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


class TestApprovalAPI:
    def test_grant_approval(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/approvals/grant",
            json={
                "workspace_id": "W1",
                "channel_id": "C1",
                "thread_ts": "123.456",
                "gate_type": "deploy",
                "approver_id": "U1",
                "approver_name": "Alice",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["gate_type"] == "deploy"
        assert data["approver_id"] == "U1"
        assert data["thread_ref"] == {
            "workspace_id": "W1",
            "channel_id": "C1",
            "thread_ts": "123.456",
        }

    def test_reject_approval(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/approvals/reject",
            json={
                "workspace_id": "W1",
                "channel_id": "C1",
                "thread_ts": "123.456",
                "gate_type": "deploy",
                "rejector_id": "U2",
                "reason": "Not ready",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["gate_type"] == "deploy"
        assert data["rejector_id"] == "U2"
        assert data["reason"] == "Not ready"
        assert data["thread_ref"] == {
            "workspace_id": "W1",
            "channel_id": "C1",
            "thread_ts": "123.456",
        }
