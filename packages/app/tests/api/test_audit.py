"""Tests for audit API."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from lintel.api.app import create_app
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


class TestAuditAPI:
    def test_create_audit_entry_returns_201(
        self,
        client: TestClient,
    ) -> None:
        resp = client.post(
            "/api/v1/audit",
            json={
                "entry_id": "a-1",
                "actor_id": "u-1",
                "actor_type": "user",
                "action": "create",
                "resource_type": "project",
                "resource_id": "proj-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["entry_id"] == "a-1"
        assert data["action"] == "create"

    def test_list_audit_entries_empty(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_audit_entry_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/audit",
            json={
                "entry_id": "a-2",
                "actor_id": "u-1",
                "actor_type": "user",
                "action": "delete",
                "resource_type": "team",
                "resource_id": "team-1",
            },
        )
        resp = client.get("/api/v1/audit/a-2")
        assert resp.status_code == 200
        assert resp.json()["action"] == "delete"

    def test_get_audit_entry_not_found(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/audit/nonexistent")
        assert resp.status_code == 404

    def test_create_duplicate_audit_entry_returns_409(
        self,
        client: TestClient,
    ) -> None:
        body = {
            "entry_id": "a-dup",
            "actor_id": "u-1",
            "actor_type": "user",
            "action": "update",
            "resource_type": "policy",
            "resource_id": "pol-1",
        }
        client.post("/api/v1/audit", json=body)
        resp = client.post("/api/v1/audit", json=body)
        assert resp.status_code == 409
