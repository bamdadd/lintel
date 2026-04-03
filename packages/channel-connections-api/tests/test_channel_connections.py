"""Tests for channel connection CRUD endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.channel_connections_api.routes import connection_store_provider, router
from lintel.channel_connections_api.store import InMemoryChannelConnectionStore

if TYPE_CHECKING:
    from collections.abc import Generator

BASE = "/api/v1/channel-connections"


@pytest.fixture()
def client() -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    store = InMemoryChannelConnectionStore()
    connection_store_provider.override(store)
    with TestClient(app) as c:
        yield c
    connection_store_provider.reset()


def _create_payload(**overrides: object) -> dict:
    defaults = {
        "provider": "slack",
        "channel_id": "C123",
        "workspace_id": "W456",
        "config": {"bot_token": "xoxb-test"},
    }
    return {**defaults, **overrides}


class TestCreateChannelConnection:
    def test_create_returns_201(self, client: TestClient) -> None:
        resp = client.post(BASE, json=_create_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider"] == "slack"
        assert data["channel_id"] == "C123"
        assert data["workspace_id"] == "W456"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_with_custom_id(self, client: TestClient) -> None:
        resp = client.post(BASE, json=_create_payload(id="custom-id"))
        assert resp.status_code == 201
        assert resp.json()["id"] == "custom-id"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        payload = _create_payload(id="dup")
        client.post(BASE, json=payload)
        resp = client.post(BASE, json=payload)
        assert resp.status_code == 409

    def test_create_requires_provider(self, client: TestClient) -> None:
        resp = client.post(BASE, json={"channel_id": "C1", "workspace_id": "W1"})
        assert resp.status_code == 422


class TestListChannelConnections:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get(BASE)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(provider="slack"))
        client.post(BASE, json=_create_payload(provider="telegram"))
        resp = client.get(BASE)
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetChannelConnection:
    def test_get_existing(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(id="conn-1"))
        resp = client.get(f"{BASE}/conn-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "conn-1"

    def test_get_not_found(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/missing")
        assert resp.status_code == 404


class TestUpdateChannelConnection:
    def test_patch_updates_fields(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(id="u1"))
        resp = client.patch(f"{BASE}/u1", json={"provider": "telegram"})
        assert resp.status_code == 200
        assert resp.json()["provider"] == "telegram"
        assert resp.json()["channel_id"] == "C123"  # unchanged

    def test_patch_updates_timestamp(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(id="u2"))
        original = client.get(f"{BASE}/u2").json()
        resp = client.patch(f"{BASE}/u2", json={"provider": "telegram"})
        assert resp.json()["updated_at"] >= original["updated_at"]

    def test_patch_not_found(self, client: TestClient) -> None:
        resp = client.patch(f"{BASE}/missing", json={"provider": "x"})
        assert resp.status_code == 404


class TestDeleteChannelConnection:
    def test_delete_existing(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(id="d1"))
        resp = client.delete(f"{BASE}/d1")
        assert resp.status_code == 204
        assert client.get(f"{BASE}/d1").status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        resp = client.delete(f"{BASE}/missing")
        assert resp.status_code == 404
