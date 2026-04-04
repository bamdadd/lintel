"""Tests for bots API."""

from fastapi.testclient import TestClient


class TestBotsAPI:
    def test_create_bot_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/bots",
            json={
                "bot_id": "b-1",
                "name": "TestBot",
                "platform": "slack",
                "scopes": ["read", "write"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["bot_id"] == "b-1"
        assert data["name"] == "TestBot"
        assert data["platform"] == "slack"
        assert data["scopes"] == ["read", "write"]
        assert data["status"] == "active"

    def test_create_bot_duplicate_returns_409(self, client: TestClient) -> None:
        client.post("/api/v1/bots", json={"bot_id": "b-dup", "name": "Bot1"})
        resp = client.post("/api/v1/bots", json={"bot_id": "b-dup", "name": "Bot2"})
        assert resp.status_code == 409

    def test_list_bots_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/bots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_bots_returns_created(self, client: TestClient) -> None:
        client.post("/api/v1/bots", json={"bot_id": "b-2", "name": "Bot2"})
        resp = client.get("/api/v1/bots")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_bot_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/bots", json={"bot_id": "b-3", "name": "Bot3"})
        resp = client.get("/api/v1/bots/b-3")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bot3"

    def test_get_bot_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/bots/nonexistent")
        assert resp.status_code == 404

    def test_update_bot(self, client: TestClient) -> None:
        client.post("/api/v1/bots", json={"bot_id": "b-4", "name": "Bot4"})
        resp = client.patch(
            "/api/v1/bots/b-4",
            json={"name": "UpdatedBot", "status": "inactive"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "UpdatedBot"
        assert data["status"] == "inactive"

    def test_update_bot_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/bots/nonexistent", json={"name": "X"})
        assert resp.status_code == 404

    def test_update_bot_scopes(self, client: TestClient) -> None:
        client.post("/api/v1/bots", json={"bot_id": "b-5", "name": "Bot5"})
        resp = client.patch(
            "/api/v1/bots/b-5",
            json={"scopes": ["admin"]},
        )
        assert resp.status_code == 200
        assert resp.json()["scopes"] == ["admin"]

    def test_delete_bot_returns_204(self, client: TestClient) -> None:
        client.post("/api/v1/bots", json={"bot_id": "b-6", "name": "Bot6"})
        resp = client.delete("/api/v1/bots/b-6")
        assert resp.status_code == 204
        assert client.get("/api/v1/bots/b-6").status_code == 404

    def test_delete_bot_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/bots/nonexistent")
        assert resp.status_code == 404
