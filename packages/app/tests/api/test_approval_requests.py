"""Tests for approval requests API."""

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


class TestApprovalRequestsAPI:
    def test_create_approval_request_returns_201(
        self,
        client: TestClient,
    ) -> None:
        resp = client.post(
            "/api/v1/approval-requests",
            json={
                "approval_id": "apr-1",
                "run_id": "run-1",
                "gate_type": "deploy",
                "requested_by": "u-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["approval_id"] == "apr-1"
        assert data["status"] == "pending"

    def test_list_approval_requests_empty(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/approval-requests")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_approval_request_by_id(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/approval-requests",
            json={
                "approval_id": "apr-2",
                "run_id": "run-1",
                "gate_type": "review",
            },
        )
        resp = client.get("/api/v1/approval-requests/apr-2")
        assert resp.status_code == 200
        assert resp.json()["approval_id"] == "apr-2"

    def test_get_approval_request_not_found(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/approval-requests/nonexistent")
        assert resp.status_code == 404

    def test_approve_approval_request(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/approval-requests",
            json={
                "approval_id": "apr-3",
                "run_id": "run-1",
                "gate_type": "deploy",
            },
        )
        resp = client.post(
            "/api/v1/approval-requests/apr-3/approve",
            json={"decided_by": "u-admin"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["decided_by"] == "u-admin"

    def test_reject_approval_request(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/approval-requests",
            json={
                "approval_id": "apr-4",
                "run_id": "run-1",
                "gate_type": "deploy",
            },
        )
        resp = client.post(
            "/api/v1/approval-requests/apr-4/reject",
            json={"decided_by": "u-admin", "reason": "Not ready"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert resp.json()["reason"] == "Not ready"
