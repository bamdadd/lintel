"""Integration tests for hook API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.api.routes.hooks import router
from lintel.event_store.in_memory import InMemoryEventStore
from lintel.triggers_api.routes import trigger_store_provider
from lintel.triggers_api.store import InMemoryTriggerStore

if TYPE_CHECKING:
    from collections.abc import Generator


HOOK_BODY: dict[str, object] = {
    "hook_id": "hook-1",
    "project_id": "proj-1",
    "name": "Pre-deploy check",
    "hook_type": "pre",
    "event_pattern": "deploy.*",
}


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryTriggerStore()
    trigger_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.event_store = InMemoryEventStore()
    with TestClient(app) as c:
        yield c
    trigger_store_provider.override(None)


class TestCreateHook:
    def test_create_hook_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/hooks", json=HOOK_BODY)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trigger_id"] == "hook-1"
        assert data["name"] == "Pre-deploy check"
        assert data["hook_type"] == "pre"
        assert data["enabled"] is True

    def test_hook_type_is_required_on_post(self, client: TestClient) -> None:
        body = {
            "hook_id": "hook-no-type",
            "project_id": "proj-1",
            "name": "Missing hook type",
            "event_pattern": "some.*",
        }
        resp = client.post("/api/v1/hooks", json=body)
        assert resp.status_code == 422

    def test_event_pattern_stored_and_retrieved(self, client: TestClient) -> None:
        body = {
            **HOOK_BODY,
            "hook_id": "hook-pattern",
            "event_pattern": "pipeline.stage.*",
        }
        resp = client.post("/api/v1/hooks", json=body)
        assert resp.status_code == 201
        assert resp.json()["event_pattern"] == "pipeline.stage.*"

        get_resp = client.get("/api/v1/hooks/hook-pattern")
        assert get_resp.status_code == 200
        assert get_resp.json()["event_pattern"] == "pipeline.stage.*"

    def test_max_chain_depth_defaults_to_5(self, client: TestClient) -> None:
        resp = client.post("/api/v1/hooks", json=HOOK_BODY)
        assert resp.status_code == 201
        assert resp.json()["max_chain_depth"] == 5

    def test_max_chain_depth_custom_value(self, client: TestClient) -> None:
        body = {**HOOK_BODY, "hook_id": "hook-depth", "max_chain_depth": 10}
        resp = client.post("/api/v1/hooks", json=body)
        assert resp.status_code == 201
        assert resp.json()["max_chain_depth"] == 10

    def test_create_duplicate_hook_returns_409(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.post("/api/v1/hooks", json=HOOK_BODY)
        assert resp.status_code == 409

    def test_trigger_type_defaults_to_webhook(self, client: TestClient) -> None:
        resp = client.post("/api/v1/hooks", json=HOOK_BODY)
        assert resp.status_code == 201
        assert resp.json()["trigger_type"] == "webhook"

    def test_create_with_condition(self, client: TestClient) -> None:
        body = {**HOOK_BODY, "hook_id": "hook-cond", "condition": "env == 'prod'"}
        resp = client.post("/api/v1/hooks", json=body)
        assert resp.status_code == 201
        assert resp.json()["condition"] == "env == 'prod'"

    def test_create_with_config(self, client: TestClient) -> None:
        body = {**HOOK_BODY, "hook_id": "hook-cfg", "config": {"url": "https://example.com"}}
        resp = client.post("/api/v1/hooks", json=body)
        assert resp.status_code == 201
        assert resp.json()["config"] == {"url": "https://example.com"}


class TestGetHook:
    def test_get_hook_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.get("/api/v1/hooks/hook-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trigger_id"] == "hook-1"
        assert data["hook_type"] == "pre"

    def test_get_nonexistent_hook_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/hooks/does-not-exist")
        assert resp.status_code == 404

    def test_get_non_hook_trigger_returns_404(self, client: TestClient) -> None:
        """A trigger without hook_type should not be accessible via /hooks/{id}."""
        from lintel.domain.types import Trigger, TriggerType

        # Directly insert a plain trigger (no hook_type) into the store
        store = trigger_store_provider.get()
        plain_trigger = Trigger(
            trigger_id="plain-t",
            project_id="proj-1",
            trigger_type=TriggerType.SLACK_MESSAGE,
            name="Plain trigger",
        )
        import asyncio

        asyncio.get_event_loop().run_until_complete(store.add(plain_trigger))

        resp = client.get("/api/v1/hooks/plain-t")
        assert resp.status_code == 404


class TestListHooks:
    def test_list_hooks_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/hooks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_hooks_returns_only_hooks(self, client: TestClient) -> None:
        """GET /hooks should only return triggers that have hook_type set."""
        import asyncio

        from lintel.domain.types import Trigger, TriggerType

        store = trigger_store_provider.get()

        # Add a plain trigger (no hook_type) directly to the store
        plain = Trigger(
            trigger_id="plain-1",
            project_id="proj-1",
            trigger_type=TriggerType.SLACK_MESSAGE,
            name="Plain",
        )
        asyncio.get_event_loop().run_until_complete(store.add(plain))

        # Add a hook via the API
        client.post("/api/v1/hooks", json=HOOK_BODY)

        resp = client.get("/api/v1/hooks")
        assert resp.status_code == 200
        hooks = resp.json()
        assert len(hooks) == 1
        assert hooks[0]["trigger_id"] == "hook-1"
        assert hooks[0]["hook_type"] == "pre"

    def test_list_hooks_multiple(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        second = {**HOOK_BODY, "hook_id": "hook-2", "name": "Post hook", "hook_type": "post"}
        client.post("/api/v1/hooks", json=second)

        resp = client.get("/api/v1/hooks")
        assert resp.status_code == 200
        hooks = resp.json()
        assert len(hooks) == 2
        hook_ids = {h["trigger_id"] for h in hooks}
        assert hook_ids == {"hook-1", "hook-2"}

    def test_list_hooks_filter_by_project(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        other = {
            **HOOK_BODY,
            "hook_id": "hook-other",
            "project_id": "proj-2",
            "name": "Other project hook",
        }
        client.post("/api/v1/hooks", json=other)

        resp = client.get("/api/v1/hooks", params={"project_id": "proj-1"})
        assert resp.status_code == 200
        hooks = resp.json()
        assert len(hooks) == 1
        assert hooks[0]["trigger_id"] == "hook-1"


class TestUpdateHook:
    def test_update_hook_name(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.put("/api/v1/hooks/hook-1", json={"name": "Updated name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated name"

    def test_update_hook_type(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.put("/api/v1/hooks/hook-1", json={"hook_type": "post"})
        assert resp.status_code == 200
        assert resp.json()["hook_type"] == "post"

    def test_update_event_pattern(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.put("/api/v1/hooks/hook-1", json={"event_pattern": "build.*"})
        assert resp.status_code == 200
        assert resp.json()["event_pattern"] == "build.*"

    def test_update_max_chain_depth(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.put("/api/v1/hooks/hook-1", json={"max_chain_depth": 3})
        assert resp.status_code == 200
        assert resp.json()["max_chain_depth"] == 3

    def test_update_nonexistent_hook_returns_404(self, client: TestClient) -> None:
        resp = client.put("/api/v1/hooks/nope", json={"name": "X"})
        assert resp.status_code == 404

    def test_update_preserves_unmodified_fields(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.put("/api/v1/hooks/hook-1", json={"name": "New name"})
        data = resp.json()
        assert data["name"] == "New name"
        assert data["hook_type"] == "pre"
        assert data["event_pattern"] == "deploy.*"
        assert data["max_chain_depth"] == 5

    def test_update_enabled_flag(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.put("/api/v1/hooks/hook-1", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False


class TestDeleteHook:
    def test_delete_hook_returns_204(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        resp = client.delete("/api/v1/hooks/hook-1")
        assert resp.status_code == 204

    def test_delete_hook_removes_from_store(self, client: TestClient) -> None:
        client.post("/api/v1/hooks", json=HOOK_BODY)
        client.delete("/api/v1/hooks/hook-1")
        resp = client.get("/api/v1/hooks/hook-1")
        assert resp.status_code == 404

    def test_delete_nonexistent_hook_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/hooks/nope")
        assert resp.status_code == 404

    def test_delete_non_hook_trigger_returns_404(self, client: TestClient) -> None:
        """Deleting a plain trigger (no hook_type) via /hooks should 404."""
        import asyncio

        from lintel.domain.types import Trigger, TriggerType

        store = trigger_store_provider.get()
        plain = Trigger(
            trigger_id="plain-del",
            project_id="proj-1",
            trigger_type=TriggerType.MANUAL,
            name="Plain to delete",
        )
        asyncio.get_event_loop().run_until_complete(store.add(plain))

        resp = client.delete("/api/v1/hooks/plain-del")
        assert resp.status_code == 404
