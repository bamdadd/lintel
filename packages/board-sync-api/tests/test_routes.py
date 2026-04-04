"""Tests for board sync API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _create_config(
    client: TestClient,
    sync_config_id: str = "sc1",
    board_id: str = "board-1",
    provider: str = "jira",
) -> dict:  # type: ignore[type-arg]
    return client.post(
        "/api/v1/board-sync/configs",
        json={
            "sync_config_id": sync_config_id,
            "board_id": board_id,
            "provider": provider,
            "direction": "bidirectional",
        },
    ).json()


class TestSyncConfigCRUD:
    def test_create_sync_config(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/board-sync/configs",
            json={
                "sync_config_id": "sc1",
                "board_id": "board-1",
                "provider": "jira",
                "direction": "pull",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sync_config_id"] == "sc1"
        assert data["provider"] == "jira"
        assert data["direction"] == "pull"
        assert data["status"] == "disconnected"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        _create_config(client, "dup")
        resp = client.post(
            "/api/v1/board-sync/configs",
            json={"sync_config_id": "dup", "board_id": "b", "provider": "jira"},
        )
        assert resp.status_code == 409

    def test_list_configs_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/board-sync/configs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_configs_with_items(self, client: TestClient) -> None:
        _create_config(client, "a")
        _create_config(client, "b")
        resp = client.get("/api/v1/board-sync/configs")
        assert len(resp.json()) == 2

    def test_list_configs_filter_by_board(self, client: TestClient) -> None:
        _create_config(client, "a", board_id="board-1")
        _create_config(client, "b", board_id="board-2")
        resp = client.get("/api/v1/board-sync/configs", params={"board_id": "board-1"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["board_id"] == "board-1"

    def test_get_config(self, client: TestClient) -> None:
        _create_config(client, "sc1")
        resp = client.get("/api/v1/board-sync/configs/sc1")
        assert resp.status_code == 200
        assert resp.json()["sync_config_id"] == "sc1"

    def test_get_config_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/board-sync/configs/missing")
        assert resp.status_code == 404

    def test_update_config(self, client: TestClient) -> None:
        _create_config(client, "sc1")
        resp = client.patch(
            "/api/v1/board-sync/configs/sc1",
            json={"direction": "push"},
        )
        assert resp.status_code == 200
        assert resp.json()["direction"] == "push"

    def test_delete_config(self, client: TestClient) -> None:
        _create_config(client, "sc1")
        resp = client.delete("/api/v1/board-sync/configs/sc1")
        assert resp.status_code == 204
        assert client.get("/api/v1/board-sync/configs/sc1").status_code == 404

    def test_delete_config_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/board-sync/configs/missing")
        assert resp.status_code == 404


class TestSyncTrigger:
    def test_trigger_sync(self, client: TestClient) -> None:
        _create_config(client, "sc1")
        resp = client.post("/api/v1/board-sync/configs/sc1/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert "pulled" in data
        assert "pushed" in data
        assert data["status"] == "connected"

    def test_trigger_sync_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/board-sync/configs/missing/sync")
        assert resp.status_code == 404


class TestMappings:
    def test_list_mappings_empty(self, client: TestClient) -> None:
        _create_config(client, "sc1")
        resp = client.get("/api/v1/board-sync/configs/sc1/mappings")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_mapping(self, client: TestClient) -> None:
        _create_config(client, "sc1")
        resp = client.post(
            "/api/v1/board-sync/configs/sc1/mappings",
            params={"work_item_id": "wi-1", "external_id": "PROJ-123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["work_item_id"] == "wi-1"
        assert data["external_id"] == "PROJ-123"

    def test_create_mapping_config_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/board-sync/configs/missing/mappings",
            params={"work_item_id": "wi-1", "external_id": "X"},
        )
        assert resp.status_code == 404

    def test_list_mappings_after_create(self, client: TestClient) -> None:
        _create_config(client, "sc1")
        client.post(
            "/api/v1/board-sync/configs/sc1/mappings",
            params={"work_item_id": "wi-1", "external_id": "PROJ-123"},
        )
        resp = client.get("/api/v1/board-sync/configs/sc1/mappings")
        assert len(resp.json()) == 1


class TestNotionProvider:
    def test_create_notion_config(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/board-sync/configs",
            json={
                "sync_config_id": "nc1",
                "board_id": "board-1",
                "provider": "notion",
                "external_database_id": "db-abc",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["provider"] == "notion"
        assert resp.json()["external_database_id"] == "db-abc"
