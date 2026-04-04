"""Tests for pipeline diagnostics API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestPipelineDiagnosticsAPI:
    def test_record_diagnostic_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/pipelines/diagnostics",
            json={
                "diagnostic_id": "diag-1",
                "pipeline_run_id": "run-1",
                "project_id": "proj-1",
                "failed_stage": "implement",
                "error_message": "Agent crashed",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["diagnostic_id"] == "diag-1"
        assert data["pipeline_run_id"] == "run-1"
        assert data["category"] == "unknown"

    def test_record_duplicate_returns_409(self, client: TestClient) -> None:
        payload = {
            "diagnostic_id": "diag-dup",
            "pipeline_run_id": "run-1",
            "failed_stage": "research",
            "error_message": "timeout",
        }
        client.post("/api/v1/pipelines/diagnostics", json=payload)
        resp = client.post("/api/v1/pipelines/diagnostics", json=payload)
        assert resp.status_code == 409

    def test_list_empty_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/pipelines/diagnostics")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_recorded_items_sorted_desc(self, client: TestClient) -> None:
        client.post(
            "/api/v1/pipelines/diagnostics",
            json={
                "diagnostic_id": "diag-a",
                "pipeline_run_id": "run-1",
                "failed_stage": "implement",
                "error_message": "err-a",
                "project_id": "proj-1",
            },
        )
        client.post(
            "/api/v1/pipelines/diagnostics",
            json={
                "diagnostic_id": "diag-b",
                "pipeline_run_id": "run-2",
                "failed_stage": "review",
                "error_message": "err-b",
                "project_id": "proj-1",
            },
        )
        resp = client.get("/api/v1/pipelines/diagnostics")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        # Most recent first
        assert items[0]["diagnostic_id"] == "diag-b"

    def test_list_filter_by_project_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/pipelines/diagnostics",
            json={
                "diagnostic_id": "diag-p1",
                "pipeline_run_id": "run-1",
                "failed_stage": "implement",
                "error_message": "err",
                "project_id": "proj-1",
            },
        )
        client.post(
            "/api/v1/pipelines/diagnostics",
            json={
                "diagnostic_id": "diag-p2",
                "pipeline_run_id": "run-2",
                "failed_stage": "review",
                "error_message": "err",
                "project_id": "proj-2",
            },
        )
        resp = client.get("/api/v1/pipelines/diagnostics", params={"project_id": "proj-1"})
        items = resp.json()
        assert len(items) == 1
        assert items[0]["project_id"] == "proj-1"

    def test_list_respects_limit(self, client: TestClient) -> None:
        for i in range(5):
            client.post(
                "/api/v1/pipelines/diagnostics",
                json={
                    "diagnostic_id": f"diag-lim-{i}",
                    "pipeline_run_id": f"run-{i}",
                    "failed_stage": "implement",
                    "error_message": "err",
                },
            )
        resp = client.get("/api/v1/pipelines/diagnostics", params={"limit": 2})
        assert len(resp.json()) == 2

    def test_get_existing_returns_200(self, client: TestClient) -> None:
        client.post(
            "/api/v1/pipelines/diagnostics",
            json={
                "diagnostic_id": "diag-get",
                "pipeline_run_id": "run-1",
                "failed_stage": "implement",
                "error_message": "err",
            },
        )
        resp = client.get("/api/v1/pipelines/diagnostics/diag-get")
        assert resp.status_code == 200
        assert resp.json()["diagnostic_id"] == "diag-get"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/pipelines/diagnostics/nonexistent")
        assert resp.status_code == 404
