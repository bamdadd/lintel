"""Tests for pipelines API."""

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app

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
        assert len(data["stages"]) == 9  # feature_to_pr has 9 stages

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
        assert len(skipped) == 9  # all pending stages get skipped

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
            "GET", f"/api/v1/pipelines/logs-run/stages/{stage_id}/logs",
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            lines = list(resp.iter_lines())
            # Should have log lines, status, outputs, and end
            data_lines = [l for l in lines if l.startswith("data:")]
            assert len(data_lines) >= 3  # at least logs + status + end
