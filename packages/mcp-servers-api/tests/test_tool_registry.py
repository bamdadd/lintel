"""Tests for the MCP tool catalog and per-project allowlist endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.mcp_servers_api.routes import (
    mcp_server_store_provider,
    mcp_tool_allowlist_store_provider,
    mcp_tool_store_provider,
    router,
)
from lintel.mcp_servers_api.store import (
    InMemoryMCPServerStore,
    MCPToolAllowlistStore,
    MCPToolStore,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    mcp_server_store_provider.override(InMemoryMCPServerStore())
    mcp_tool_store_provider.override(MCPToolStore())
    mcp_tool_allowlist_store_provider.override(MCPToolAllowlistStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    mcp_server_store_provider.override(None)
    mcp_tool_store_provider.override(None)
    mcp_tool_allowlist_store_provider.override(None)


class TestMCPToolCatalog:
    def test_register_tool(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/mcp-tools",
            json={
                "tool_id": "tool-1",
                "server_id": "srv-1",
                "name": "read_file",
                "description": "Read a file from the sandbox",
                "security_classification": "standard",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tool_id"] == "tool-1"
        assert data["name"] == "read_file"
        assert data["security_classification"] == "standard"
        assert data["enabled"] is True

    def test_register_duplicate_tool(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "dup-1", "server_id": "srv-1", "name": "t1"},
        )
        resp = client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "dup-1", "server_id": "srv-1", "name": "t2"},
        )
        assert resp.status_code == 409

    def test_list_tools(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "t1", "server_id": "srv-1", "name": "tool_a"},
        )
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "t2", "server_id": "srv-2", "name": "tool_b"},
        )
        resp = client.get("/api/v1/mcp-tools")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_tools_by_server(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "t1", "server_id": "srv-1", "name": "a"},
        )
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "t2", "server_id": "srv-2", "name": "b"},
        )
        resp = client.get("/api/v1/mcp-tools?server_id=srv-1")
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) == 1
        assert tools[0]["server_id"] == "srv-1"

    def test_list_tools_by_classification(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={
                "tool_id": "t1",
                "server_id": "s1",
                "name": "safe",
                "security_classification": "standard",
            },
        )
        client.post(
            "/api/v1/mcp-tools",
            json={
                "tool_id": "t2",
                "server_id": "s1",
                "name": "danger",
                "security_classification": "destructive",
            },
        )
        resp = client.get("/api/v1/mcp-tools?classification=destructive")
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) == 1
        assert tools[0]["name"] == "danger"

    def test_get_tool(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "get-1", "server_id": "s1", "name": "get_tool"},
        )
        resp = client.get("/api/v1/mcp-tools/get-1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get_tool"

    def test_get_tool_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/mcp-tools/missing")
        assert resp.status_code == 404

    def test_delete_tool(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "del-1", "server_id": "s1", "name": "del"},
        )
        resp = client.delete("/api/v1/mcp-tools/del-1")
        assert resp.status_code == 204
        resp = client.get("/api/v1/mcp-tools/del-1")
        assert resp.status_code == 404

    def test_delete_tool_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/mcp-tools/missing")
        assert resp.status_code == 404


class TestMCPToolAllowlist:
    def test_set_allowlist(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/projects/proj-1/mcp-tool-allowlist",
            json={"tool_ids": ["t1", "t2"], "description": "Project tools"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-1"
        assert data["tool_ids"] == ["t1", "t2"]

    def test_get_allowlist(self, client: TestClient) -> None:
        client.put(
            "/api/v1/projects/proj-1/mcp-tool-allowlist",
            json={"tool_ids": ["t1"]},
        )
        resp = client.get("/api/v1/projects/proj-1/mcp-tool-allowlist")
        assert resp.status_code == 200
        assert resp.json()["tool_ids"] == ["t1"]

    def test_get_allowlist_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/no-proj/mcp-tool-allowlist")
        assert resp.status_code == 404

    def test_delete_allowlist(self, client: TestClient) -> None:
        client.put(
            "/api/v1/projects/proj-1/mcp-tool-allowlist",
            json={"tool_ids": ["t1"]},
        )
        resp = client.delete("/api/v1/projects/proj-1/mcp-tool-allowlist")
        assert resp.status_code == 204
        resp = client.get("/api/v1/projects/proj-1/mcp-tool-allowlist")
        assert resp.status_code == 404

    def test_delete_allowlist_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/projects/no-proj/mcp-tool-allowlist")
        assert resp.status_code == 404

    def test_replace_allowlist(self, client: TestClient) -> None:
        client.put(
            "/api/v1/projects/proj-1/mcp-tool-allowlist",
            json={"allowlist_id": "al-1", "tool_ids": ["t1"]},
        )
        client.put(
            "/api/v1/projects/proj-1/mcp-tool-allowlist",
            json={"allowlist_id": "al-2", "tool_ids": ["t2", "t3"]},
        )
        resp = client.get("/api/v1/projects/proj-1/mcp-tool-allowlist")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_ids"] == ["t2", "t3"]


class TestProjectToolResolution:
    def test_resolve_all_tools_no_allowlist(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "t1", "server_id": "s1", "name": "a"},
        )
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "t2", "server_id": "s1", "name": "b"},
        )
        resp = client.get("/api/v1/projects/proj-1/mcp-tools")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_resolve_filtered_by_allowlist(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "t1", "server_id": "s1", "name": "allowed"},
        )
        client.post(
            "/api/v1/mcp-tools",
            json={"tool_id": "t2", "server_id": "s1", "name": "blocked"},
        )
        client.put(
            "/api/v1/projects/proj-1/mcp-tool-allowlist",
            json={"tool_ids": ["t1"]},
        )
        resp = client.get("/api/v1/projects/proj-1/mcp-tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) == 1
        assert tools[0]["tool_id"] == "t1"

    def test_resolve_excludes_disabled_tools(self, client: TestClient) -> None:
        client.post(
            "/api/v1/mcp-tools",
            json={
                "tool_id": "t1",
                "server_id": "s1",
                "name": "enabled",
                "enabled": True,
            },
        )
        client.post(
            "/api/v1/mcp-tools",
            json={
                "tool_id": "t2",
                "server_id": "s1",
                "name": "disabled",
                "enabled": False,
            },
        )
        resp = client.get("/api/v1/projects/proj-1/mcp-tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) == 1
        assert tools[0]["name"] == "enabled"

    def test_resolve_empty_when_no_tools(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/proj-1/mcp-tools")
        assert resp.status_code == 200
        assert resp.json() == []
