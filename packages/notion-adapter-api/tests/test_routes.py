"""Tests for Notion adapter API."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from lintel.notion_adapter_api.routes import webhook_secret_provider

if TYPE_CHECKING:
    from collections.abc import Generator


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
    """Tests for the Notion webhook endpoint."""

    def test_webhook_no_database_id_returns_ignored(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/notion/webhook",
            json={"type": "page.updated", "data": {"id": "page-1"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "no database_id in payload"

    def test_webhook_no_matching_connection_returns_ignored(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/notion/webhook",
            json={
                "type": "page.updated",
                "data": {
                    "id": "page-1",
                    "parent": {"database_id": "db-unknown"},
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "no matching connection"

    def test_webhook_triggers_pull_sync(self, client: TestClient) -> None:
        """When a matching connection exists, the webhook triggers a pull sync."""
        # Register a connection first
        client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-wh",
                "project_id": "proj-1",
                "database_id": "db-sync",
                "api_key": "ntn_key",
            },
        )

        from lintel.notion_adapter_api.sync_engine import SyncResult

        mock_result = SyncResult(pulled=3)

        with (
            patch(
                "lintel.notion_adapter_api.routes.pull_work_items",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_pull,
            patch(
                "lintel.notion_adapter_api.routes.NotionClient",
            ) as mock_client_cls,
        ):
            mock_ctx = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/integrations/notion/webhook",
                json={
                    "type": "page.updated",
                    "data": {
                        "id": "page-42",
                        "parent": {"database_id": "db-sync"},
                    },
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "synced"
        assert data["connection_id"] == "conn-wh"
        assert data["pulled"] == "3"
        mock_pull.assert_awaited_once_with(mock_ctx, "db-sync")

    def test_webhook_reports_sync_errors(self, client: TestClient) -> None:
        client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-err",
                "project_id": "proj-1",
                "database_id": "db-err",
                "api_key": "ntn_key",
            },
        )

        from lintel.notion_adapter_api.sync_engine import SyncResult

        mock_result = SyncResult(pulled=0, errors=["Pull failed: timeout"])

        with (
            patch(
                "lintel.notion_adapter_api.routes.pull_work_items",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "lintel.notion_adapter_api.routes.NotionClient",
            ) as mock_client_cls,
        ):
            mock_ctx = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/integrations/notion/webhook",
                json={
                    "type": "page.updated",
                    "data": {
                        "id": "p-1",
                        "parent": {"database_id": "db-err"},
                    },
                },
            )

        data = resp.json()
        assert data["status"] == "synced"
        assert data["pulled"] == "0"
        assert "timeout" in data["errors"]

    def test_webhook_invalid_json_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/notion/webhook",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_webhook_updates_last_synced_at(self, client: TestClient) -> None:
        """After a successful webhook sync, last_synced_at is updated."""
        client.post(
            "/api/v1/integrations/notion/connect",
            json={
                "connection_id": "conn-ts",
                "project_id": "proj-1",
                "database_id": "db-ts",
                "api_key": "ntn_key",
            },
        )

        from lintel.notion_adapter_api.sync_engine import SyncResult

        with (
            patch(
                "lintel.notion_adapter_api.routes.pull_work_items",
                new_callable=AsyncMock,
                return_value=SyncResult(pulled=1),
            ),
            patch(
                "lintel.notion_adapter_api.routes.NotionClient",
            ) as mock_client_cls,
        ):
            mock_ctx = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client.post(
                "/api/v1/integrations/notion/webhook",
                json={
                    "type": "page.updated",
                    "data": {
                        "id": "p-1",
                        "parent": {"database_id": "db-ts"},
                    },
                },
            )

        # Verify last_synced_at was set by checking the store
        import asyncio

        from lintel.notion_adapter_api.routes import notion_connection_store_provider

        store = notion_connection_store_provider.get()
        conn = asyncio.get_event_loop().run_until_complete(store.get("conn-ts"))
        assert conn is not None
        assert conn.last_synced_at is not None


class TestWebhookSignatureVerification:
    """Tests for webhook signature verification."""

    @pytest.fixture()
    def signed_client(self) -> Generator[TestClient]:
        """Client with webhook secret configured."""
        from fastapi import FastAPI

        from lintel.notion_adapter_api.routes import notion_connection_store_provider, router
        from lintel.notion_adapter_api.store import InMemoryNotionConnectionStore

        store = InMemoryNotionConnectionStore()
        notion_connection_store_provider.override(store)
        webhook_secret_provider.override("test-webhook-secret")

        app = FastAPI()
        app.state.event_bus = AsyncMock()
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as c:
            yield c
        notion_connection_store_provider.override(None)
        webhook_secret_provider.override(None)

    def test_valid_signature_accepted(self, signed_client: TestClient) -> None:
        body = json.dumps({"type": "page.updated", "data": {"id": "p1"}}).encode()
        sig = hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()

        resp = signed_client.post(
            "/api/v1/integrations/notion/webhook",
            content=body,
            headers={
                "content-type": "application/json",
                "x-notion-signature": sig,
            },
        )
        assert resp.status_code == 200

    def test_invalid_signature_rejected(self, signed_client: TestClient) -> None:
        body = json.dumps({"type": "page.updated", "data": {"id": "p1"}}).encode()

        resp = signed_client.post(
            "/api/v1/integrations/notion/webhook",
            content=body,
            headers={
                "content-type": "application/json",
                "x-notion-signature": "bad-signature",
            },
        )
        assert resp.status_code == 401

    def test_missing_signature_rejected(self, signed_client: TestClient) -> None:
        resp = signed_client.post(
            "/api/v1/integrations/notion/webhook",
            json={"type": "page.updated", "data": {"id": "p1"}},
        )
        assert resp.status_code == 401

    def test_no_secret_configured_skips_verification(self, client: TestClient) -> None:
        """When no webhook secret is configured, signature check is skipped."""
        resp = client.post(
            "/api/v1/integrations/notion/webhook",
            json={"type": "page.updated", "data": {"id": "p1"}},
        )
        assert resp.status_code == 200
