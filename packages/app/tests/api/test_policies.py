"""Tests for policies API."""

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


class TestPoliciesAPI:
    def test_create_policy_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/policies",
            json={
                "policy_id": "pol-1",
                "name": "Deploy Gate",
                "action": "require_approval",
                "approvers": ["u-1"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_id"] == "pol-1"
        assert data["name"] == "Deploy Gate"
        assert data["approvers"] == ["u-1"]

    def test_list_policies_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/policies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_policy_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/policies",
            json={
                "policy_id": "pol-2",
                "name": "Review Gate",
            },
        )
        resp = client.get("/api/v1/policies/pol-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Review Gate"

    def test_get_policy_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/policies/nonexistent")
        assert resp.status_code == 404

    def test_delete_policy_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/policies",
            json={
                "policy_id": "pol-3",
                "name": "To Delete",
            },
        )
        resp = client.delete("/api/v1/policies/pol-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/policies/pol-3").status_code == 404
