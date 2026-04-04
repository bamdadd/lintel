"""Tests for channel connection CRUD endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.channel_connections_api.routes import connection_store_provider, router
from lintel.channel_connections_api.store import InMemoryChannelConnectionStore
from lintel.channel_connections_api.types import ChannelConnection

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
        "channel_type": "slack",
        "credential_ref": "cred:slack:main",
        "workspace_id": "W456",
        "config": {"bot_token": "xoxb-test"},
    }
    return {**defaults, **overrides}


class TestCreateChannelConnection:
    def test_create_returns_201(self, client: TestClient) -> None:
        resp = client.post(BASE, json=_create_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["channel_type"] == "slack"
        assert data["credential_ref"] == "cred:slack:main"
        assert data["workspace_id"] == "W456"
        assert data["enabled"] is True
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

    def test_create_requires_channel_type(self, client: TestClient) -> None:
        resp = client.post(BASE, json={"workspace_id": "W1"})
        assert resp.status_code == 422

    def test_create_with_all_fields(self, client: TestClient) -> None:
        resp = client.post(
            BASE,
            json=_create_payload(
                team_id="team-1",
                org_id="org-1",
                allowed_workflows=["wf-1"],
                allowed_agent_roles=["coder"],
                project_ids=["proj-1"],
                bot_username="mybot",
                webhook_url="https://example.com/hook",
                enabled=False,
            ),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["team_id"] == "team-1"
        assert data["org_id"] == "org-1"
        assert data["allowed_workflows"] == ["wf-1"]
        assert data["allowed_agent_roles"] == ["coder"]
        assert data["project_ids"] == ["proj-1"]
        assert data["bot_username"] == "mybot"
        assert data["webhook_url"] == "https://example.com/hook"
        assert data["enabled"] is False


class TestListChannelConnections:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get(BASE)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(channel_type="slack"))
        client.post(BASE, json=_create_payload(channel_type="telegram"))
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
        resp = client.patch(f"{BASE}/u1", json={"channel_type": "telegram"})
        assert resp.status_code == 200
        assert resp.json()["channel_type"] == "telegram"
        assert resp.json()["workspace_id"] == "W456"  # unchanged

    def test_patch_updates_timestamp(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(id="u2"))
        original = client.get(f"{BASE}/u2").json()
        resp = client.patch(f"{BASE}/u2", json={"channel_type": "telegram"})
        assert resp.json()["updated_at"] >= original["updated_at"]

    def test_patch_not_found(self, client: TestClient) -> None:
        resp = client.patch(f"{BASE}/missing", json={"channel_type": "x"})
        assert resp.status_code == 404

    def test_patch_enable_disable(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(id="u3"))
        resp = client.patch(f"{BASE}/u3", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_patch_bot_username(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(id="u4"))
        resp = client.patch(f"{BASE}/u4", json={"bot_username": "newbot"})
        assert resp.status_code == 200
        assert resp.json()["bot_username"] == "newbot"


class TestDeleteChannelConnection:
    def test_delete_existing(self, client: TestClient) -> None:
        client.post(BASE, json=_create_payload(id="d1"))
        resp = client.delete(f"{BASE}/d1")
        assert resp.status_code == 204
        assert client.get(f"{BASE}/d1").status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        resp = client.delete(f"{BASE}/missing")
        assert resp.status_code == 404


class TestStoreFindByChannelType:
    """Test the find_by_channel_type store method directly."""

    @pytest.fixture()
    def store(self) -> InMemoryChannelConnectionStore:
        return InMemoryChannelConnectionStore()

    async def test_find_by_type_returns_matches(
        self, store: InMemoryChannelConnectionStore
    ) -> None:
        await store.add(ChannelConnection(id="s1", channel_type="slack"))
        await store.add(ChannelConnection(id="t1", channel_type="telegram"))
        await store.add(ChannelConnection(id="s2", channel_type="slack"))
        result = await store.find_by_channel_type("slack")
        assert len(result) == 2
        assert {c.id for c in result} == {"s1", "s2"}

    async def test_find_by_type_filters_disabled(
        self, store: InMemoryChannelConnectionStore
    ) -> None:
        await store.add(ChannelConnection(id="s1", channel_type="slack", enabled=True))
        await store.add(ChannelConnection(id="s2", channel_type="slack", enabled=False))
        result = await store.find_by_channel_type("slack", enabled_only=True)
        assert len(result) == 1
        assert result[0].id == "s1"

    async def test_find_by_type_includes_disabled(
        self, store: InMemoryChannelConnectionStore
    ) -> None:
        await store.add(ChannelConnection(id="s1", channel_type="slack", enabled=False))
        result = await store.find_by_channel_type("slack", enabled_only=False)
        assert len(result) == 1
