"""Tests for Notion adapter API."""

from fastapi.testclient import TestClient


class TestNotionConnectAPI:
    def test_connect_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-1",
                "project_id": "proj-1",
                "database_id": "db-abc",
                "api_key": "ntn_test_key",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["connection_id"] == "conn-1"
        assert data["project_id"] == "proj-1"
        assert data["database_id"] == "db-abc"

    def test_connect_duplicate_returns_409(self, client: TestClient) -> None:
        payload = {
            "connection_id": "conn-dup",
            "project_id": "proj-1",
            "database_id": "db-abc",
            "api_key": "ntn_test_key",
        }
        client.post("/api/v1/integrations/notion/connect", json=payload)
        resp = client.post("/api/v1/integrations/notion/connect", json=payload)
        assert resp.status_code == 409


class TestNotionSyncAPI:
    def test_sync_unknown_connection_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/notion/sync",
            json={"connection_id": "missing", "direction": "push"},
        )
        assert resp.status_code == 404


class TestNotionWebhookAPI:
    def test_webhook_returns_ok(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/notion/webhook",
            json={"type": "page.updated", "data": {"id": "page-1"}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
