"""Tests for channel adapter registry CRUD and routing endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.channel_adapter_registry_api.routes import adapter_store_provider, router
from lintel.channel_adapter_registry_api.store import InMemoryChannelAdapterStore

if TYPE_CHECKING:
    from collections.abc import Generator

BASE = "/api/v1/channel-adapters"


@pytest.fixture()
def client() -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    store = InMemoryChannelAdapterStore()
    adapter_store_provider.override(store)
    with TestClient(app) as c:
        yield c
    adapter_store_provider.reset()


def test_create_adapter(client: TestClient) -> None:
    resp = client.post(
        BASE,
        json={
            "bot_id": "bot-1",
            "connection_id": "conn-1",
            "channel_type": "slack",
            "priority": 10,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["bot_id"] == "bot-1"
    assert data["connection_id"] == "conn-1"
    assert data["channel_type"] == "slack"
    assert data["priority"] == 10
    assert data["enabled"] is True


def test_create_duplicate_id(client: TestClient) -> None:
    payload = {
        "id": "dup-1",
        "bot_id": "bot-1",
        "connection_id": "conn-1",
        "channel_type": "slack",
    }
    client.post(BASE, json=payload)
    resp = client.post(BASE, json=payload)
    assert resp.status_code == 409


def test_create_duplicate_bot_connection(client: TestClient) -> None:
    client.post(
        BASE,
        json={
            "id": "a1",
            "bot_id": "bot-1",
            "connection_id": "conn-1",
            "channel_type": "slack",
        },
    )
    resp = client.post(
        BASE,
        json={
            "id": "a2",
            "bot_id": "bot-1",
            "connection_id": "conn-1",
            "channel_type": "slack",
        },
    )
    assert resp.status_code == 409


def test_list_adapters(client: TestClient) -> None:
    assert client.get(BASE).json() == []
    client.post(
        BASE,
        json={"bot_id": "b1", "connection_id": "c1", "channel_type": "slack"},
    )
    items = client.get(BASE).json()
    assert len(items) == 1


def test_get_adapter(client: TestClient) -> None:
    resp = client.post(
        BASE,
        json={"id": "a1", "bot_id": "b1", "connection_id": "c1", "channel_type": "slack"},
    )
    assert resp.status_code == 201
    got = client.get(f"{BASE}/a1")
    assert got.status_code == 200
    assert got.json()["id"] == "a1"


def test_get_adapter_not_found(client: TestClient) -> None:
    resp = client.get(f"{BASE}/missing")
    assert resp.status_code == 404


def test_route_adapter(client: TestClient) -> None:
    client.post(
        BASE,
        json={
            "id": "low",
            "bot_id": "b1",
            "connection_id": "c1",
            "channel_type": "slack",
            "priority": 1,
        },
    )
    client.post(
        BASE,
        json={
            "id": "high",
            "bot_id": "b1",
            "connection_id": "c2",
            "channel_type": "slack",
            "priority": 10,
        },
    )
    resp = client.post(
        f"{BASE}/route",
        json={"bot_id": "b1", "channel_type": "slack"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "high"


def test_route_adapter_not_found(client: TestClient) -> None:
    resp = client.post(
        f"{BASE}/route",
        json={"bot_id": "b1", "channel_type": "slack"},
    )
    assert resp.status_code == 404


def test_route_skips_disabled(client: TestClient) -> None:
    client.post(
        BASE,
        json={
            "id": "disabled",
            "bot_id": "b1",
            "connection_id": "c1",
            "channel_type": "slack",
            "enabled": False,
            "priority": 100,
        },
    )
    resp = client.post(
        f"{BASE}/route",
        json={"bot_id": "b1", "channel_type": "slack"},
    )
    assert resp.status_code == 404
