"""Tests for triggers API."""

from fastapi.testclient import TestClient


class TestTriggersAPI:
    def test_create_trigger_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/triggers",
            json={
                "trigger_id": "t-1",
                "project_id": "proj-1",
                "trigger_type": "slack_message",
                "name": "My Trigger",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["trigger_id"] == "t-1"
        assert data["name"] == "My Trigger"
        assert data["enabled"] is True

    def test_list_triggers_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/triggers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_trigger_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/triggers",
            json={
                "trigger_id": "t-2",
                "project_id": "proj-1",
                "trigger_type": "slack_message",
                "name": "Trigger 2",
            },
        )
        resp = client.get("/api/v1/triggers/t-2")
        assert resp.status_code == 200
        assert resp.json()["trigger_id"] == "t-2"

    def test_get_trigger_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/triggers/nonexistent")
        assert resp.status_code == 404

    def test_delete_trigger_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/triggers",
            json={
                "trigger_id": "t-3",
                "project_id": "proj-1",
                "trigger_type": "slack_message",
                "name": "To Delete",
            },
        )
        resp = client.delete("/api/v1/triggers/t-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/triggers/t-3").status_code == 404

    def test_create_duplicate_trigger_returns_409(
        self,
        client: TestClient,
    ) -> None:
        body = {
            "trigger_id": "t-dup",
            "project_id": "proj-1",
            "trigger_type": "slack_message",
            "name": "Dup",
        }
        client.post("/api/v1/triggers", json=body)
        resp = client.post("/api/v1/triggers", json=body)
        assert resp.status_code == 409
