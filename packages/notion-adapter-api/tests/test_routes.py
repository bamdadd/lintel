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


class TestListConnectionsAPI:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/integrations/notion/connections")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_connections(self, client: TestClient) -> None:
        client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-1",
                "project_id": "proj-1",
                "database_id": "db-abc",
                "api_key": "ntn_key",
            },
        )
        resp = client.get("/api/v1/integrations/notion/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["connection_id"] == "conn-1"
        # API key should NOT be in the response
        assert "api_key" not in data[0]

    def test_list_filter_by_project(self, client: TestClient) -> None:
        client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-a",
                "project_id": "proj-1",
                "database_id": "db-1",
                "api_key": "k",
            },
        )
        client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-b",
                "project_id": "proj-2",
                "database_id": "db-2",
                "api_key": "k",
            },
        )
        resp = client.get(
            "/api/v1/integrations/notion/connections",
            params={"project_id": "proj-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["connection_id"] == "conn-a"


class TestGetConnectionAPI:
    def test_get_existing(self, client: TestClient) -> None:
        client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-g",
                "project_id": "proj-1",
                "database_id": "db-abc",
                "api_key": "ntn_key",
            },
        )
        resp = client.get("/api/v1/integrations/notion/connections/conn-g")
        assert resp.status_code == 200
        assert resp.json()["connection_id"] == "conn-g"
        assert "api_key" not in resp.json()

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/integrations/notion/connections/no-such")
        assert resp.status_code == 404


class TestDeleteConnectionAPI:
    def test_delete_existing(self, client: TestClient) -> None:
        client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-d",
                "project_id": "proj-1",
                "database_id": "db-abc",
                "api_key": "ntn_key",
            },
        )
        resp = client.delete("/api/v1/integrations/notion/connections/conn-d")
        assert resp.status_code == 204
        # Verify it's gone
        resp = client.get("/api/v1/integrations/notion/connections/conn-d")
        assert resp.status_code == 404

    def test_delete_missing_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/integrations/notion/connections/no-such")
        assert resp.status_code == 404


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
