"""Tests for pipelines API."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from lintel.api.app import create_app
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_pipeline(
    client: TestClient,
    run_id: str = "run1",
) -> dict:
    return client.post(
        "/api/v1/pipelines",
        json={
            "run_id": run_id,
            "project_id": "proj-1",
            "work_item_id": "wi-1",
        },
    ).json()


class TestPipelinesAPI:
    def test_create_pipeline(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/pipelines",
            json={
                "run_id": "run1",
                "project_id": "proj-1",
                "work_item_id": "wi-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["run_id"] == "run1"
        assert data["project_id"] == "proj-1"
        assert data["status"] == "pending"
        assert len(data["stages"]) == 11  # feature_to_pr has 11 stages

    def test_create_pipeline_duplicate_returns_409(
        self,
        client: TestClient,
    ) -> None:
        _create_pipeline(client, "dup")
        resp = client.post(
            "/api/v1/pipelines",
            json={
                "run_id": "dup",
                "project_id": "p",
                "work_item_id": "w",
            },
        )
        assert resp.status_code == 409

    def test_list_pipelines_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/pipelines")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_pipelines_with_items(self, client: TestClient) -> None:
        _create_pipeline(client, "a")
        _create_pipeline(client, "b")
        resp = client.get("/api/v1/pipelines")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_pipeline_by_id(self, client: TestClient) -> None:
        _create_pipeline(client, "run1")
        resp = client.get("/api/v1/pipelines/run1")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run1"

    def test_get_pipeline_not_found_returns_404(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/pipelines/missing")
        assert resp.status_code == 404

    def test_cancel_pipeline(self, client: TestClient) -> None:
        _create_pipeline(client, "run1")
        resp = client.post("/api/v1/pipelines/run1/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        skipped = [s for s in data["stages"] if s["status"] == "skipped"]
        assert len(skipped) == 11  # all pending stages get skipped

    def test_delete_pipeline(self, client: TestClient) -> None:
        _create_pipeline(client, "run1")
        resp = client.delete("/api/v1/pipelines/run1")
        assert resp.status_code == 204
        assert client.get("/api/v1/pipelines/run1").status_code == 404

    def test_retry_stage_resets_to_running(self, client: TestClient) -> None:
        """REQ-1.7: Retry a failed stage."""
        data = _create_pipeline(client, "retry-run")
        stage_id = data["stages"][0]["stage_id"]
        # Manually set stage to failed via cancel + re-create approach
        # Instead, use the stage detail and mark it failed
        # Simplest: get the store and update directly
        store = client.app.state.pipeline_store  # type: ignore[union-attr]
        import asyncio
        from dataclasses import replace as dc_replace

        from lintel.contracts.types import StageStatus

        async def _fail_stage() -> None:
            run = await store.get("retry-run")
            stages = list(run.stages)
            stages[0] = dc_replace(stages[0], status=StageStatus.FAILED, error="boom")
            await store.update(dc_replace(run, stages=tuple(stages)))

        asyncio.get_event_loop().run_until_complete(_fail_stage())

        resp = client.post(f"/api/v1/pipelines/retry-run/stages/{stage_id}/retry")
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "running"
        assert result["retry_count"] == 1
        assert result["error"] == ""

    def test_retry_stage_rejects_pending(self, client: TestClient) -> None:
        data = _create_pipeline(client, "retry-pending")
        stage_id = data["stages"][0]["stage_id"]
        resp = client.post(f"/api/v1/pipelines/retry-pending/stages/{stage_id}/retry")
        assert resp.status_code == 409

    def test_stage_logs_endpoint_returns_sse(self, client: TestClient) -> None:
        """REQ-1.6: Stage logs SSE endpoint returns data."""
        data = _create_pipeline(client, "logs-run")
        stage_id = data["stages"][0]["stage_id"]
        # Mark stage as succeeded so the SSE stream terminates
        store = client.app.state.pipeline_store  # type: ignore[union-attr]
        import asyncio
        from dataclasses import replace as dc_replace

        from lintel.contracts.types import StageStatus

        async def _succeed_stage() -> None:
            run = await store.get("logs-run")
            stages = list(run.stages)
            stages[0] = dc_replace(
                stages[0],
                status=StageStatus.SUCCEEDED,
                logs=("line 1", "line 2"),
                outputs={"result": "ok"},
            )
            await store.update(dc_replace(run, stages=tuple(stages)))

        asyncio.get_event_loop().run_until_complete(_succeed_stage())

        with client.stream(
            "GET",
            f"/api/v1/pipelines/logs-run/stages/{stage_id}/logs",
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            lines = list(resp.iter_lines())
            # Should have log lines, status, outputs, and end
            data_lines = [line for line in lines if line.startswith("data:")]
            assert len(data_lines) >= 3  # at least logs + status + end

    def test_reject_stage_sets_failed(self, client: TestClient) -> None:
        """Rejecting a waiting_approval stage fails the pipeline."""
        data = _create_pipeline(client, "reject-run")
        stage_id = data["stages"][3]["stage_id"]  # approval_gate_research
        # Set stage to waiting_approval
        store = client.app.state.pipeline_store  # type: ignore[union-attr]
        import asyncio
        from dataclasses import replace as dc_replace

        from lintel.contracts.types import PipelineStatus, StageStatus

        async def _wait_stage() -> None:
            run = await store.get("reject-run")
            stages = list(run.stages)
            stages[3] = dc_replace(stages[3], status=StageStatus.WAITING_APPROVAL)
            await store.update(
                dc_replace(run, stages=tuple(stages), status=PipelineStatus.WAITING_APPROVAL),
            )

        asyncio.get_event_loop().run_until_complete(_wait_stage())

        resp = client.post(f"/api/v1/pipelines/reject-run/stages/{stage_id}/reject")
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "rejected"

        # Pipeline should be failed
        run_resp = client.get("/api/v1/pipelines/reject-run")
        run_data = run_resp.json()
        assert run_data["status"] == "failed"

        # Remaining pending stages should be skipped
        skipped = [s for s in run_data["stages"] if s["status"] == "skipped"]
        assert len(skipped) > 0

    def test_reject_stage_rejects_non_waiting(self, client: TestClient) -> None:
        """Cannot reject a stage that is not waiting_approval."""
        data = _create_pipeline(client, "reject-bad")
        stage_id = data["stages"][0]["stage_id"]
        resp = client.post(f"/api/v1/pipelines/reject-bad/stages/{stage_id}/reject")
        assert resp.status_code == 409

    # --- REQ-013: Stage Report Editing ---

    def test_edit_stage_report(self, client: TestClient) -> None:
        """PATCH report updates stage outputs and returns version."""
        data = _create_pipeline(client, "edit-run")
        # research stage is index 3
        stage_id = data["stages"][3]["stage_id"]
        store = client.app.state.pipeline_store  # type: ignore[union-attr]
        import asyncio
        from dataclasses import replace as dc_replace

        from lintel.contracts.types import StageStatus

        async def _succeed() -> None:
            run = await store.get("edit-run")
            stages = list(run.stages)
            stages[3] = dc_replace(
                stages[3],
                status=StageStatus.SUCCEEDED,
                outputs={"research_report": "original report"},
            )
            await store.update(dc_replace(run, stages=tuple(stages)))

        asyncio.get_event_loop().run_until_complete(_succeed())

        resp = client.patch(
            f"/api/v1/pipelines/edit-run/stages/{stage_id}/report",
            json={"content": "edited report", "editor": "alice"},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["version"] == 1
        assert result["content"] == "edited report"
        assert result["report_key"] == "research_report"

    def test_edit_report_rejects_pending_stage(self, client: TestClient) -> None:
        """Cannot edit a pending stage report."""
        data = _create_pipeline(client, "edit-pending")
        stage_id = data["stages"][1]["stage_id"]
        resp = client.patch(
            f"/api/v1/pipelines/edit-pending/stages/{stage_id}/report",
            json={"content": "nope"},
        )
        assert resp.status_code == 409

    def test_report_versions_empty(self, client: TestClient) -> None:
        """No versions before any edits."""
        data = _create_pipeline(client, "ver-run")
        stage_id = data["stages"][1]["stage_id"]
        resp = client.get(
            f"/api/v1/pipelines/ver-run/stages/{stage_id}/report/versions",
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_report_versions_accumulate(self, client: TestClient) -> None:
        """Multiple edits create version history."""
        data = _create_pipeline(client, "ver2-run")
        stage_id = data["stages"][3]["stage_id"]
        store = client.app.state.pipeline_store  # type: ignore[union-attr]
        import asyncio
        from dataclasses import replace as dc_replace

        from lintel.contracts.types import StageStatus

        async def _succeed() -> None:
            run = await store.get("ver2-run")
            stages = list(run.stages)
            stages[3] = dc_replace(
                stages[3],
                status=StageStatus.SUCCEEDED,
                outputs={"research_report": "v0"},
            )
            await store.update(dc_replace(run, stages=tuple(stages)))

        asyncio.get_event_loop().run_until_complete(_succeed())

        client.patch(
            f"/api/v1/pipelines/ver2-run/stages/{stage_id}/report",
            json={"content": "v1"},
        )
        client.patch(
            f"/api/v1/pipelines/ver2-run/stages/{stage_id}/report",
            json={"content": "v2"},
        )

        resp = client.get(
            f"/api/v1/pipelines/ver2-run/stages/{stage_id}/report/versions",
        )
        versions = resp.json()
        assert len(versions) == 2
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2
        assert versions[1]["content"] == "v2"

    def test_regenerate_stage(self, client: TestClient) -> None:
        """Regenerate resets stage to running with guidance."""
        data = _create_pipeline(client, "regen-run")
        stage_id = data["stages"][3]["stage_id"]
        store = client.app.state.pipeline_store  # type: ignore[union-attr]
        import asyncio
        from dataclasses import replace as dc_replace

        from lintel.contracts.types import StageStatus

        async def _succeed() -> None:
            run = await store.get("regen-run")
            stages = list(run.stages)
            stages[3] = dc_replace(
                stages[3],
                status=StageStatus.SUCCEEDED,
                outputs={"research_report": "old"},
            )
            await store.update(dc_replace(run, stages=tuple(stages)))

        asyncio.get_event_loop().run_until_complete(_succeed())

        resp = client.post(
            f"/api/v1/pipelines/regen-run/stages/{stage_id}/regenerate",
            json={"guidance": "also check auth module"},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "running"
        assert result["retry_count"] == 1
        assert result["inputs"]["regenerate_guidance"] == "also check auth module"
        assert result["outputs"] is None

    def test_regenerate_rejects_pending(self, client: TestClient) -> None:
        """Cannot regenerate a pending stage."""
        data = _create_pipeline(client, "regen-bad")
        stage_id = data["stages"][1]["stage_id"]
        resp = client.post(
            f"/api/v1/pipelines/regen-bad/stages/{stage_id}/regenerate",
            json={},
        )
        assert resp.status_code == 409

    # --- REQ-3.3: Pipeline SSE Events ---

    def test_pipeline_events_sse_endpoint(self, client: TestClient) -> None:
        """SSE endpoint emits stage status changes."""
        _create_pipeline(client, "sse-run")
        # Cancel the pipeline so it reaches a terminal state and the SSE stream ends
        client.post("/api/v1/pipelines/sse-run/cancel")

        with client.stream("GET", "/api/v1/pipelines/sse-run/events") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            lines = list(resp.iter_lines())
            data_lines = [ln for ln in lines if ln.startswith("data:")]
            # Should emit stage_update for skipped stages + pipeline_status + pipeline_complete
            assert len(data_lines) >= 2

    def test_pipeline_events_not_found(self, client: TestClient) -> None:
        """SSE endpoint returns 404 for missing pipeline."""
        resp = client.get("/api/v1/pipelines/missing/events")
        assert resp.status_code == 404
