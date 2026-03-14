"""Tests for the debug endpoint."""

from __future__ import annotations

import asyncio
from typing import Any

from httpx import ASGITransport, AsyncClient
import pytest

from lintel.api.app import create_app


@pytest.fixture
def app() -> Any:  # noqa: ANN401
    return create_app()


@pytest.fixture
async def client(app: Any) -> AsyncClient:  # noqa: ANN401
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


class TestListNodes:
    async def test_returns_available_nodes(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/debug/nodes")
        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data["nodes"]
        assert "implement" in data["nodes"]
        assert "research" in data["nodes"]
        assert len(data["nodes"]) >= 8

    async def test_includes_descriptions(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/debug/nodes")
        data = resp.json()
        assert "descriptions" in data
        assert "plan" in data["descriptions"]


class TestRunNodeDispatch:
    async def test_unknown_node_returns_failed(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/debug/run-node",
            json={"node_name": "nonexistent", "prompt": "hello"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["run_id"] == ""

    async def test_valid_node_returns_immediately(self, client: AsyncClient) -> None:
        """Valid node dispatch returns run_id and stage_id immediately."""
        resp = await client.post(
            "/api/v1/debug/run-node",
            json={"node_name": "ingest", "prompt": "Fix the login bug"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["run_id"] != ""
        assert data["stage_id"] != ""
        assert data["node_name"] == "ingest"
        # Give the background task a moment to complete
        await asyncio.sleep(0.2)

    async def test_plan_node_dispatches(self, client: AsyncClient) -> None:
        """Plan node dispatch returns immediately with running status."""
        resp = await client.post(
            "/api/v1/debug/run-node",
            json={"node_name": "plan", "prompt": "Add a login page"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["run_id"] != ""
        assert data["node_name"] == "plan"
        await asyncio.sleep(0.2)

    async def test_route_node_dispatches(self, client: AsyncClient) -> None:
        """Route node dispatch returns immediately."""
        resp = await client.post(
            "/api/v1/debug/run-node",
            json={
                "node_name": "route",
                "prompt": "Add OAuth support",
                "intent": "feature",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["run_id"] != ""
        await asyncio.sleep(0.2)

    async def test_response_includes_stage_id(self, client: AsyncClient) -> None:
        """Response must include stage_id for SSE log streaming."""
        resp = await client.post(
            "/api/v1/debug/run-node",
            json={"node_name": "ingest", "prompt": "test"},
        )
        data = resp.json()
        assert "stage_id" in data
        assert len(data["stage_id"]) > 0
        await asyncio.sleep(0.2)
