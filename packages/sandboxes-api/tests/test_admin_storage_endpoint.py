"""Tests for GET /admin/sandbox-storage endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.api.routes.admin import router

if TYPE_CHECKING:
    from collections.abc import Generator


class FakeSandboxStore:
    """In-memory sandbox store for testing."""

    def __init__(self, sandboxes: list[dict[str, Any]] | None = None) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        for sb in sandboxes or []:
            self._data[sb["sandbox_id"]] = dict(sb)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def get(self, sandbox_id: str) -> dict[str, Any] | None:
        return self._data.get(sandbox_id)

    async def update(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        self._data[sandbox_id] = metadata

    async def remove(self, sandbox_id: str) -> None:
        self._data.pop(sandbox_id, None)


@pytest.fixture()
def client_with_sandboxes() -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    store = FakeSandboxStore(
        [
            {
                "sandbox_id": "sb-1",
                "storage_limit_gb": 4,
                "storage_usage_bytes": 1_073_741_824,  # 1 GB
                "storage_checked_at": "2026-04-01T12:00:00+00:00",
                "scheduled_cleanup_at": None,
            },
            {
                "sandbox_id": "sb-2",
                "storage_limit_gb": 10,
                "storage_usage_bytes": None,
                "storage_checked_at": None,
                "scheduled_cleanup_at": "2026-04-02T12:00:00+00:00",
            },
        ]
    )
    app.state.sandbox_store = store
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_empty() -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c


class TestAdminSandboxStorageEndpoint:
    def test_returns_storage_data(self, client_with_sandboxes: TestClient) -> None:
        resp = client_with_sandboxes.get("/api/v1/admin/sandbox-storage")
        assert resp.status_code == 200
        data = resp.json()
        assert "sandboxes" in data
        assert len(data["sandboxes"]) == 2

        sb1 = data["sandboxes"][0]
        assert sb1["sandbox_id"] == "sb-1"
        assert sb1["usage_bytes"] == 1_073_741_824
        assert sb1["limit_bytes"] == 4 * 1024 * 1024 * 1024
        assert sb1["available_bytes"] == 4 * 1024 * 1024 * 1024 - 1_073_741_824
        assert sb1["last_checked_at"] == "2026-04-01T12:00:00+00:00"

    def test_null_usage_defaults_to_zero(self, client_with_sandboxes: TestClient) -> None:
        resp = client_with_sandboxes.get("/api/v1/admin/sandbox-storage")
        data = resp.json()
        sb2 = data["sandboxes"][1]
        assert sb2["sandbox_id"] == "sb-2"
        assert sb2["usage_bytes"] == 0
        assert sb2["limit_bytes"] == 10 * 1024 * 1024 * 1024
        assert sb2["available_bytes"] == 10 * 1024 * 1024 * 1024
        assert sb2["last_checked_at"] is None
        assert sb2["scheduled_cleanup_at"] == "2026-04-02T12:00:00+00:00"

    def test_empty_store(self, client_empty: TestClient) -> None:
        resp = client_empty.get("/api/v1/admin/sandbox-storage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sandboxes"] == []
