"""Tests for users API."""

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


class TestUsersAPI:
    def test_create_user_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/users",
            json={
                "user_id": "u-1",
                "name": "Alice",
                "email": "alice@example.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "u-1"
        assert data["name"] == "Alice"
        assert data["role"] == "member"

    def test_list_users_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_user_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/users",
            json={
                "user_id": "u-2",
                "name": "Bob",
            },
        )
        resp = client.get("/api/v1/users/u-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bob"

    def test_get_user_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/nonexistent")
        assert resp.status_code == 404

    def test_delete_user_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/users",
            json={
                "user_id": "u-3",
                "name": "Charlie",
            },
        )
        resp = client.delete("/api/v1/users/u-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/users/u-3").status_code == 404
