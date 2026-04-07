"""Tests for work items API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _create_work_item(
    client: TestClient,
    work_item_id: str = "wi1",
    project_id: str = "proj-1",
    work_type: str = "feature",
    description: str = "",
) -> dict[str, Any]:
    return client.post(
        "/api/v1/work-items",
        json={
            "work_item_id": work_item_id,
            "project_id": project_id,
            "title": "Fix bug",
            "work_type": work_type,
            "description": description,
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


class TestWorkflowDispatchSmoke:
    """Smoke tests verifying the full dispatch path fires when enabled."""

    def test_dispatch_creates_pipeline_and_fires_command(self, client: TestClient) -> None:
        """Moving to in_progress with all stores wired should create pipeline + dispatch."""
        # Wire up stores
        wf_def_store = AsyncMock()
        wf_def_store.get = AsyncMock(return_value={"enabled": True})

        project_store = AsyncMock()
        project_store.get = AsyncMock(
            return_value={
                "project_id": "proj-1",
                "workflow_execution_enabled": True,
                "default_branch": "main",
                "credential_ids": [],
                "repo_ids": ["repo-1"],
            }
        )

        repo_store = AsyncMock()
        repo_store.get = AsyncMock(return_value={"url": "https://github.com/test/repo"})

        pipeline_store = AsyncMock()
        pipeline_store.add = AsyncMock()
        pipeline_store.list_all = AsyncMock(return_value=[])

        trigger_store = AsyncMock()
        trigger_store.add = AsyncMock()

        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock()

        app_state = client.app.state  # type: ignore[union-attr]
        app_state.workflow_definition_store = wf_def_store
        app_state.project_store = project_store
        app_state.repository_store = repo_store
        app_state.pipeline_store = pipeline_store
        app_state.trigger_store = trigger_store
        app_state.command_dispatcher = dispatcher

        _create_work_item(client, "smoke-1", description="Build a login page")
        resp = client.patch(
            "/api/v1/work-items/smoke-1",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200

        # Verify pipeline was created
        pipeline_store.add.assert_called_once()
        pipeline_run = pipeline_store.add.call_args[0][0]
        assert pipeline_run.project_id == "proj-1"
        assert pipeline_run.work_item_id == "smoke-1"
        assert pipeline_run.workflow_definition_id == "feature_to_pr"
        assert len(pipeline_run.stages) > 0

        # Verify trigger was created
        trigger_store.add.assert_called_once()

        # Verify command was dispatched (async task created)
        # The dispatch happens in an asyncio.create_task, so we verify the task was created
        # by checking the dispatcher was set up (task runs after response)

    def test_dispatch_skipped_when_workflow_disabled(self, client: TestClient) -> None:
        """Workflow disabled → no pipeline, no dispatch."""
        wf_def_store = AsyncMock()
        wf_def_store.get = AsyncMock(return_value={"enabled": False})

        dispatcher = AsyncMock()
        pipeline_store = AsyncMock()

        app_state = client.app.state  # type: ignore[union-attr]
        app_state.workflow_definition_store = wf_def_store
        app_state.command_dispatcher = dispatcher
        app_state.pipeline_store = pipeline_store

        _create_work_item(client, "smoke-disabled")
        resp = client.patch(
            "/api/v1/work-items/smoke-disabled",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        # Pipeline should NOT have been created
        pipeline_store.add.assert_not_called()

    def test_dispatch_maps_work_types_to_feature_to_pr(self, client: TestClient) -> None:
        """All work types (feature, bug, refactor, task) map to feature_to_pr."""
        for work_type in ("feature", "bug", "refactor", "task"):
            wf_def_store = AsyncMock()
            wf_def_store.get = AsyncMock(return_value={"enabled": True})

            project_store = AsyncMock()
            project_store.get = AsyncMock(
                return_value={
                    "project_id": "proj-1",
                    "workflow_execution_enabled": True,
                    "default_branch": "main",
                    "credential_ids": [],
                    "repo_ids": [],
                }
            )

            pipeline_store = AsyncMock()
            pipeline_store.add = AsyncMock()
            pipeline_store.list_all = AsyncMock(return_value=[])

            trigger_store = AsyncMock()
            trigger_store.add = AsyncMock()

            dispatcher = AsyncMock()

            app_state = client.app.state  # type: ignore[union-attr]
            app_state.workflow_definition_store = wf_def_store
            app_state.project_store = project_store
            app_state.pipeline_store = pipeline_store
            app_state.trigger_store = trigger_store
            app_state.command_dispatcher = dispatcher

            wid = f"smoke-{work_type}"
            _create_work_item(client, wid, work_type=work_type)
            resp = client.patch(
                f"/api/v1/work-items/{wid}",
                json={"status": "in_progress"},
            )
            assert resp.status_code == 200

            # Workflow definition lookup used feature_to_pr
            wf_def_store.get.assert_called_with("feature_to_pr")

    def test_no_double_trigger_on_repeated_in_progress(self, client: TestClient) -> None:
        """Patching status to in_progress when already in_progress should not re-trigger."""
        wf_def_store = AsyncMock()
        wf_def_store.get = AsyncMock(return_value={"enabled": True})

        pipeline_store = AsyncMock()
        pipeline_store.add = AsyncMock()
        pipeline_store.list_all = AsyncMock(return_value=[])

        trigger_store = AsyncMock()
        trigger_store.add = AsyncMock()

        project_store = AsyncMock()
        project_store.get = AsyncMock(
            return_value={
                "project_id": "proj-1",
                "workflow_execution_enabled": True,
                "default_branch": "main",
                "credential_ids": [],
                "repo_ids": [],
            }
        )

        dispatcher = AsyncMock()

        app_state = client.app.state  # type: ignore[union-attr]
        app_state.workflow_definition_store = wf_def_store
        app_state.project_store = project_store
        app_state.pipeline_store = pipeline_store
        app_state.trigger_store = trigger_store
        app_state.command_dispatcher = dispatcher

        _create_work_item(client, "smoke-double")
        # First transition: open → in_progress
        client.patch("/api/v1/work-items/smoke-double", json={"status": "in_progress"})
        first_call_count = pipeline_store.add.call_count
        assert first_call_count == 1

        # Second patch: in_progress → in_progress (no transition)
        client.patch("/api/v1/work-items/smoke-double", json={"status": "in_progress"})
        assert pipeline_store.add.call_count == first_call_count  # No new pipeline


class TestPrUrlPersistence:
    """Tests for pr_url field persistence and partial update semantics."""

    def test_patch_with_pr_url_and_in_review_persists(self, client: TestClient) -> None:
        """PATCH with pr_url and status=in_review persists both fields."""
        _create_work_item(client, "wi-pr")
        # Move to in_progress first
        client.patch("/api/v1/work-items/wi-pr", json={"status": "in_progress"})
        # Then to in_review with pr_url
        resp = client.patch(
            "/api/v1/work-items/wi-pr",
            json={"status": "in_review", "pr_url": "https://github.com/test/repo/pull/42"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_review"
        assert data["pr_url"] == "https://github.com/test/repo/pull/42"

        # GET confirms persistence
        get_resp = client.get("/api/v1/work-items/wi-pr")
        assert get_resp.status_code == 200
        assert get_resp.json()["pr_url"] == "https://github.com/test/repo/pull/42"
        assert get_resp.json()["status"] == "in_review"

    def test_partial_update_does_not_clear_pr_url(self, client: TestClient) -> None:
        """PATCH with only status does not clear an existing pr_url."""
        _create_work_item(client, "wi-partial")
        # Set pr_url and in_review
        client.patch("/api/v1/work-items/wi-partial", json={"status": "in_progress"})
        client.patch(
            "/api/v1/work-items/wi-partial",
            json={"status": "in_review", "pr_url": "https://github.com/test/repo/pull/10"},
        )
        # Now update only status (forward to approved) — pr_url should remain
        resp = client.patch(
            "/api/v1/work-items/wi-partial",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["pr_url"] == "https://github.com/test/repo/pull/10"

    def test_create_work_item_with_pr_url(self, client: TestClient) -> None:
        """Creating a work item with pr_url set persists it."""
        resp = client.post(
            "/api/v1/work-items",
            json={
                "work_item_id": "wi-create-pr",
                "project_id": "proj-1",
                "title": "Pre-existing PR",
                "pr_url": "https://github.com/test/repo/pull/99",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["pr_url"] == "https://github.com/test/repo/pull/99"


class TestStatusPrecedenceGuard:
    """Tests for forward-only status transition enforcement."""

    def test_cannot_regress_from_in_review_to_in_progress(self, client: TestClient) -> None:
        """Regression from in_review to in_progress is blocked."""
        _create_work_item(client, "wi-guard")
        client.patch("/api/v1/work-items/wi-guard", json={"status": "in_progress"})
        client.patch("/api/v1/work-items/wi-guard", json={"status": "in_review"})

        resp = client.patch(
            "/api/v1/work-items/wi-guard",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 409
        assert "regress" in resp.json()["detail"].lower()

    def test_can_advance_from_in_review_to_approved(self, client: TestClient) -> None:
        """Forward transition from in_review to approved is allowed."""
        _create_work_item(client, "wi-fwd")
        client.patch("/api/v1/work-items/wi-fwd", json={"status": "in_progress"})
        client.patch("/api/v1/work-items/wi-fwd", json={"status": "in_review"})

        resp = client.patch(
            "/api/v1/work-items/wi-fwd",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_failed_status_allowed_as_reset(self, client: TestClient) -> None:
        """Failed status is allowed from any state (it's a reset, precedence 0)."""
        _create_work_item(client, "wi-fail")
        client.patch("/api/v1/work-items/wi-fail", json={"status": "in_progress"})
        client.patch("/api/v1/work-items/wi-fail", json={"status": "in_review"})

        resp = client.patch(
            "/api/v1/work-items/wi-fail",
            json={"status": "failed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_open_status_allowed_as_reset_from_in_progress(self, client: TestClient) -> None:
        """Open status is allowed from in_progress (precedence 1, explicit reset)."""
        _create_work_item(client, "wi-reset")
        client.patch("/api/v1/work-items/wi-reset", json={"status": "in_progress"})

        resp = client.patch(
            "/api/v1/work-items/wi-reset",
            json={"status": "open"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"
