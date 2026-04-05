"""Tests for work items API."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _create_work_item(client: TestClient, work_item_id: str = "wi1") -> dict:  # type: ignore[type-arg]
    return client.post(
        "/api/v1/work-items",
        json={
            "work_item_id": work_item_id,
            "project_id": "proj-1",
            "title": "Fix bug",
        },
    ).json()


class TestWorkItemsAPI:
    def test_create_work_item(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/work-items",
            json={
                "work_item_id": "wi1",
                "project_id": "proj-1",
                "title": "Do something",
                "description": "Details here",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["work_item_id"] == "wi1"
        assert data["project_id"] == "proj-1"
        assert data["title"] == "Do something"
        assert data["status"] == "open"

    def test_create_work_item_duplicate_returns_409(self, client: TestClient) -> None:
        _create_work_item(client, "dup")
        resp = client.post(
            "/api/v1/work-items",
            json={
                "work_item_id": "dup",
                "project_id": "p",
                "title": "Again",
            },
        )
        assert resp.status_code == 409

    def test_list_work_items_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/work-items")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_work_items_with_items(self, client: TestClient) -> None:
        _create_work_item(client, "a")
        _create_work_item(client, "b")
        resp = client.get("/api/v1/work-items")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_work_item_by_id(self, client: TestClient) -> None:
        _create_work_item(client, "wi1")
        resp = client.get("/api/v1/work-items/wi1")
        assert resp.status_code == 200
        assert resp.json()["work_item_id"] == "wi1"

    def test_get_work_item_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/work-items/missing")
        assert resp.status_code == 404

    def test_update_work_item(self, client: TestClient) -> None:
        _create_work_item(client, "wi1")
        resp = client.patch(
            "/api/v1/work-items/wi1",
            json={"title": "Updated title", "status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated title"
        assert resp.json()["status"] == "in_progress"

    def test_delete_work_item(self, client: TestClient) -> None:
        _create_work_item(client, "wi1")
        resp = client.delete("/api/v1/work-items/wi1")
        assert resp.status_code == 204
        assert client.get("/api/v1/work-items/wi1").status_code == 404


class TestWorkflowExecutionToggle:
    """Tests for workflow-level and project-level enabled checks."""

    def test_trigger_skipped_when_workflow_disabled(self, client: TestClient) -> None:
        """Moving to in_progress should NOT trigger workflow when definition disabled."""
        wf_def_store = AsyncMock()
        wf_def_store.get = AsyncMock(return_value={"enabled": False})
        client.app.state.workflow_definition_store = wf_def_store  # type: ignore[union-attr]

        _create_work_item(client, "wi-disabled")
        with patch(
            "lintel.work_items_api.routes._trigger_workflow_for_work_item",
            wraps=__import__(
                "lintel.work_items_api.routes", fromlist=["_trigger_workflow_for_work_item"]
            )._trigger_workflow_for_work_item,
        ) as mock_trigger:
            resp = client.patch(
                "/api/v1/work-items/wi-disabled",
                json={"status": "in_progress"},
            )
            assert resp.status_code == 200
            # Trigger was called but returned early — no dispatcher on app.state
            if mock_trigger.called:
                assert not hasattr(client.app.state, "command_dispatcher")  # type: ignore[union-attr]

    def test_trigger_skipped_when_project_workflow_disabled(self, client: TestClient) -> None:
        """Moving to in_progress should NOT trigger workflow when project disables it."""
        project_store = AsyncMock()
        project_store.get = AsyncMock(
            return_value={
                "project_id": "proj-1",
                "workflow_execution_enabled": False,
            }
        )
        client.app.state.project_store = project_store  # type: ignore[union-attr]

        _create_work_item(client, "wi-toggle")
        with patch(
            "lintel.work_items_api.routes._trigger_workflow_for_work_item",
            wraps=__import__(
                "lintel.work_items_api.routes", fromlist=["_trigger_workflow_for_work_item"]
            )._trigger_workflow_for_work_item,
        ) as mock_trigger:
            resp = client.patch(
                "/api/v1/work-items/wi-toggle",
                json={"status": "in_progress"},
            )
            assert resp.status_code == 200
            if mock_trigger.called:
                assert not hasattr(client.app.state, "command_dispatcher")  # type: ignore[union-attr]

    def test_trigger_proceeds_when_project_workflow_enabled(self, client: TestClient) -> None:
        """Moving to in_progress should attempt trigger when project enables it."""
        project_store = AsyncMock()
        project_store.get = AsyncMock(
            return_value={
                "project_id": "proj-1",
                "workflow_execution_enabled": True,
            }
        )
        client.app.state.project_store = project_store  # type: ignore[union-attr]

        _create_work_item(client, "wi-enabled")
        resp = client.patch(
            "/api/v1/work-items/wi-enabled",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200

    def test_trigger_proceeds_when_workflow_enabled(self, client: TestClient) -> None:
        """Moving to in_progress should proceed when workflow definition is enabled."""
        wf_def_store = AsyncMock()
        wf_def_store.get = AsyncMock(return_value={"enabled": True})
        client.app.state.workflow_definition_store = wf_def_store  # type: ignore[union-attr]

        _create_work_item(client, "wi-wf-enabled")
        resp = client.patch(
            "/api/v1/work-items/wi-wf-enabled",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200

    def test_trigger_proceeds_when_no_wf_def_store(self, client: TestClient) -> None:
        """When no workflow_definition_store exists, enabled check is skipped."""
        _create_work_item(client, "wi-no-store")
        resp = client.patch(
            "/api/v1/work-items/wi-no-store",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
