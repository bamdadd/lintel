"""Tests for the approval request resolve endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.approval_requests_api.routes import (
    approval_request_store_provider,
    router,
)
from lintel.approval_requests_api.store import InMemoryApprovalRequestStore


@pytest.fixture
def client() -> TestClient:
    store = InMemoryApprovalRequestStore()
    approval_request_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    yield TestClient(app)
    approval_request_store_provider.override(None)


@pytest.fixture
def seeded_client(client: TestClient) -> TestClient:
    """Client with a pre-existing pending approval request."""
    client.post(
        "/api/v1/approval-requests",
        json={
            "approval_id": "test-ap-1",
            "run_id": "run-1",
            "gate_type": "spec_approval",
            "requested_by": "system",
            "confidence": 0.5,
            "threshold": 0.85,
        },
    )
    return client


class TestResolveEndpoint:
    def test_resolve_approve(self, seeded_client: TestClient) -> None:
        resp = seeded_client.post(
            "/api/v1/approval-requests/test-ap-1/resolve",
            json={
                "decision": "approve",
                "decided_by": "admin",
                "comment": "looks good",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["decided_by"] == "admin"

    def test_resolve_reject(self, seeded_client: TestClient) -> None:
        resp = seeded_client.post(
            "/api/v1/approval-requests/test-ap-1/resolve",
            json={
                "decision": "reject",
                "decided_by": "admin",
                "comment": "needs work",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    def test_resolve_with_correction(
        self,
        seeded_client: TestClient,
    ) -> None:
        resp = seeded_client.post(
            "/api/v1/approval-requests/test-ap-1/resolve",
            json={
                "decision": "approve",
                "decided_by": "admin",
                "correction": {"field": "summary", "value": "fixed"},
                "reasoning": "summary was wrong",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["correction"] == {
            "field": "summary",
            "value": "fixed",
        }

    def test_resolve_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/approval-requests/nonexistent/resolve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 404

    def test_resolve_already_resolved(
        self,
        seeded_client: TestClient,
    ) -> None:
        # Approve first
        seeded_client.post(
            "/api/v1/approval-requests/test-ap-1/resolve",
            json={"decision": "approve", "decided_by": "admin"},
        )
        # Try again
        resp = seeded_client.post(
            "/api/v1/approval-requests/test-ap-1/resolve",
            json={"decision": "reject", "decided_by": "admin"},
        )
        assert resp.status_code == 409

    def test_resolve_invalid_decision(
        self,
        seeded_client: TestClient,
    ) -> None:
        resp = seeded_client.post(
            "/api/v1/approval-requests/test-ap-1/resolve",
            json={"decision": "maybe"},
        )
        assert resp.status_code == 422
