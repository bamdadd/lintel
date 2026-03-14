"""Integration tests for FastAPI API layer."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from lintel.api.app import create_app
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


async def test_correlation_id_propagation(client: AsyncClient) -> None:
    corr_id = str(uuid4())
    response = await client.get("/healthz", headers={"X-Correlation-ID": corr_id})
    assert response.headers["X-Correlation-ID"] == corr_id


async def test_correlation_id_generated_when_missing(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert "X-Correlation-ID" in response.headers
    # Should be a valid UUID
    from uuid import UUID

    UUID(response.headers["X-Correlation-ID"])


async def test_threads_list_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/threads")
    assert response.status_code == 200
    assert response.json() == []


async def test_events_list_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events")
    assert response.status_code == 200
    assert response.json() == []
