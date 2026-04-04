"""Tests for background agent session routes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from lintel.background_agents_api.routes import router, session_store_provider
from lintel.background_agents_api.store import InMemoryBackgroundSessionStore


@pytest.fixture()
def store() -> InMemoryBackgroundSessionStore:
    return InMemoryBackgroundSessionStore()


@pytest.fixture()
def app(store: InMemoryBackgroundSessionStore) -> FastAPI:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    session_store_provider.override(store)
    return application


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_start_session(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_role": "coder", "task": "implement X"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_role"] == "coder"
    assert data["task"] == "implement X"
    assert data["session_id"]
    assert data["status"] in ("pending", "running", "completed")


async def test_list_sessions(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/agents/sessions",
        json={"agent_role": "coder", "task": "task 1"},
    )
    await client.post(
        "/api/v1/agents/sessions",
        json={"agent_role": "reviewer", "task": "task 2"},
    )
    # Allow background tasks to complete
    await asyncio.sleep(0.05)

    resp = await client.get("/api/v1/agents/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


async def test_list_sessions_filter_by_status(
    client: AsyncClient, store: InMemoryBackgroundSessionStore
) -> None:
    resp = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_role": "coder", "task": "task 1"},
    )
    session_id = resp.json()["session_id"]
    await asyncio.sleep(0.05)

    # After background task runs, session should be completed
    resp = await client.get("/api/v1/agents/sessions", params={"status": "completed"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(s["session_id"] == session_id for s in data)


async def test_get_session(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_role": "coder", "task": "do stuff"},
    )
    session_id = resp.json()["session_id"]
    await asyncio.sleep(0.05)

    resp = await client.get(f"/api/v1/agents/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert "logs" in data
    assert len(data["logs"]) > 0


async def test_get_session_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/agents/sessions/nonexistent")
    assert resp.status_code == 404


async def test_stop_session(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_role": "coder", "task": "work"},
    )
    session_id = resp.json()["session_id"]

    resp = await client.delete(f"/api/v1/agents/sessions/{session_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/agents/sessions/{session_id}")
    assert resp.status_code == 404


async def test_stop_session_not_found(client: AsyncClient) -> None:
    resp = await client.delete("/api/v1/agents/sessions/nonexistent")
    assert resp.status_code == 404
