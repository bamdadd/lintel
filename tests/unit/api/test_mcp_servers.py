"""Tests for the MCP server management API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestMCPServersAPI:
    def test_create_mcp_server(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/mcp-servers",
            json={
                "server_id": "test-mcp-1",
                "name": "Test MCP Server",
                "url": "http://localhost:9000/mcp",
                "description": "A test server",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["server_id"] == "test-mcp-1"
        assert data["name"] == "Test MCP Server"
        assert data["url"] == "http://localhost:9000/mcp"
        assert data["enabled"] is True

    def test_list_mcp_servers(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-servers",
            json={"name": "S1", "url": "http://localhost:9001/mcp"},
        )
        client.post(
            "/api/v1/mcp-servers",
            json={"name": "S2", "url": "http://localhost:9002/mcp"},
        )
        resp = client.get("/api/v1/mcp-servers")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_mcp_server(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-servers",
            json={"server_id": "get-test", "name": "Get Test", "url": "http://localhost:9003/mcp"},
        )
        resp = client.get("/api/v1/mcp-servers/get-test")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test"

    def test_get_mcp_server_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/mcp-servers/nonexistent")
        assert resp.status_code == 404

    def test_update_mcp_server(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-servers",
            json={"server_id": "upd-1", "name": "Original", "url": "http://localhost:9004/mcp"},
        )
        resp = client.patch(
            "/api/v1/mcp-servers/upd-1",
            json={"name": "Updated", "enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["enabled"] is False

    def test_delete_mcp_server(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-servers",
            json={"server_id": "del-1", "name": "Delete Me", "url": "http://localhost:9005/mcp"},
        )
        resp = client.delete("/api/v1/mcp-servers/del-1")
        assert resp.status_code == 204
        resp = client.get("/api/v1/mcp-servers/del-1")
        assert resp.status_code == 404

    def test_delete_mcp_server_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/mcp-servers/nonexistent")
        assert resp.status_code == 404

    def test_create_duplicate(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-servers",
            json={"server_id": "dup-1", "name": "First", "url": "http://localhost:9006/mcp"},
        )
        resp = client.post(
            "/api/v1/mcp-servers",
            json={"server_id": "dup-1", "name": "Second", "url": "http://localhost:9007/mcp"},
        )
        assert resp.status_code == 409
