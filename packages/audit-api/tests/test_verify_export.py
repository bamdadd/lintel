"""Tests for audit verify and export endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.audit_api.hash_chain import HashChainAuditStore
from lintel.audit_api.routes import audit_entry_store_provider, router

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def chain_client() -> Generator[TestClient]:
    store = HashChainAuditStore()
    audit_entry_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    audit_entry_store_provider.override(None)


def _post_entry(client: TestClient, entry_id: str, ts: str = "") -> None:
    client.post(
        "/api/v1/audit",
        json={
            "entry_id": entry_id,
            "actor_id": "u-1",
            "actor_type": "user",
            "action": "create",
            "resource_type": "project",
            "resource_id": "proj-1",
            "timestamp": ts,
        },
    )


class TestVerifyEndpoint:
    def test_verify_empty_chain(self, chain_client: TestClient) -> None:
        resp = chain_client.get("/api/v1/audit/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["entries_checked"] == 0

    def test_verify_valid_chain(self, chain_client: TestClient) -> None:
        _post_entry(chain_client, "a-1", ts="2025-01-01T00:00:00")
        _post_entry(chain_client, "a-2", ts="2025-01-02T00:00:00")
        resp = chain_client.get("/api/v1/audit/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["entries_checked"] == 2


class TestExportEndpoint:
    def test_export_all(self, chain_client: TestClient) -> None:
        _post_entry(chain_client, "a-1", ts="2025-01-01T00:00:00")
        _post_entry(chain_client, "a-2", ts="2025-01-02T00:00:00")
        resp = chain_client.get("/api/v1/audit/export")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2

    def test_export_with_date_filter(self, chain_client: TestClient) -> None:
        _post_entry(chain_client, "a-1", ts="2025-01-01T00:00:00")
        _post_entry(chain_client, "a-2", ts="2025-01-05T00:00:00")
        _post_entry(chain_client, "a-3", ts="2025-01-10T00:00:00")
        resp = chain_client.get(
            "/api/v1/audit/export",
            params={"from_ts": "2025-01-02T00:00:00", "to_ts": "2025-01-06T00:00:00"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["entry_id"] == "a-2"

    def test_export_includes_hash(self, chain_client: TestClient) -> None:
        _post_entry(chain_client, "a-1", ts="2025-01-01T00:00:00")
        resp = chain_client.get("/api/v1/audit/export")
        data = resp.json()
        assert data["items"][0]["previous_hash"] is not None

    def test_export_empty(self, chain_client: TestClient) -> None:
        resp = chain_client.get("/api/v1/audit/export")
        assert resp.status_code == 200
        assert resp.json()["items"] == []
