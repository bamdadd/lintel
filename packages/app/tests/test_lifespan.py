"""Integration tests for the app lifespan and composition root wiring.

Validates that the FastAPI application can start up with in-memory stores,
that StoreProvider instances are wired, and that core services are available
on ``app.state`` after lifespan initialisation.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _force_memory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the in-memory storage backend is used for all tests."""
    monkeypatch.setenv("LINTEL_STORAGE_BACKEND", "memory")
    # Clear any postgres DSN so lifespan never tries to connect
    monkeypatch.delenv("LINTEL_DB_DSN", raising=False)


@pytest.fixture
async def app_client() -> AsyncGenerator[AsyncClient]:
    """Create an ASGI test client with the full lifespan wired up."""
    from httpx import ASGITransport, AsyncClient

    from lintel.api.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_health_endpoint(app_client: AsyncClient) -> None:
    """The health endpoint should respond 200 after lifespan completes."""
    resp = await app_client.get("/health")
    assert resp.status_code == 200


async def test_store_wiring_resolves() -> None:
    """StoreProvider instances should resolve after lifespan runs."""
    from lintel.api.app import create_app

    os.environ.setdefault("LINTEL_STORAGE_BACKEND", "memory")
    app = create_app()

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Trigger lifespan by making a request
            await client.get("/health")

        # After lifespan, verify key stores are on app.state
        assert hasattr(app.state, "event_store"), "event_store missing from app.state"
        assert hasattr(app.state, "user_store"), "user_store missing from app.state"
        assert hasattr(app.state, "pipeline_store"), "pipeline_store missing from app.state"


async def test_event_bus_on_app_state() -> None:
    """The event bus should be available on app.state after startup."""
    from lintel.api.app import create_app

    os.environ.setdefault("LINTEL_STORAGE_BACKEND", "memory")
    app = create_app()

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/health")

        assert hasattr(app.state, "event_bus"), "event_bus missing from app.state"
