"""Tests for workspace CRUD routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestCreateWorkspace:
    def test_create_workspace(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/workspaces",
            json={"name": "Acme Corp", "slug": "acme", "owner_user_id": "u1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["slug"] == "acme"
        assert data["owner_user_id"] == "u1"
        assert "workspace_id" in data
        assert "created_at" in data

    def test_create_duplicate_id(self, client: TestClient) -> None:
        payload = {
            "workspace_id": "ws-1",
            "name": "Acme",
            "slug": "acme",
            "owner_user_id": "u1",
        }
        client.post("/api/v1/workspaces", json=payload)
        resp = client.post("/api/v1/workspaces", json=payload)
        assert resp.status_code == 409

    def test_create_duplicate_slug(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workspaces",
            json={"name": "Acme", "slug": "acme", "owner_user_id": "u1"},
        )
        resp = client.post(
            "/api/v1/workspaces",
            json={"name": "Acme 2", "slug": "acme", "owner_user_id": "u2"},
        )
        assert resp.status_code == 409
        assert "slug" in resp.json()["detail"].lower()


class TestListWorkspaces:
    def test_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspaces")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_create(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workspaces",
            json={"name": "W1", "slug": "w1", "owner_user_id": "u1"},
        )
        client.post(
            "/api/v1/workspaces",
            json={"name": "W2", "slug": "w2", "owner_user_id": "u1"},
        )
        resp = client.get("/api/v1/workspaces")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetWorkspace:
    def test_get_existing(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_id": "ws-42",
                "name": "Test",
                "slug": "test",
                "owner_user_id": "u1",
            },
        )
        assert create_resp.status_code == 201
        resp = client.get("/api/v1/workspaces/ws-42")
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] == "ws-42"

    def test_get_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspaces/nonexistent")
        assert resp.status_code == 404
