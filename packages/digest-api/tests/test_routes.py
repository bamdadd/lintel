"""Tests for digest API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from conftest import FakePipelineStore, FakeWorkItemStore


class TestDigestAPI:
    def test_create_digest_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/digests",
            json={
                "id": "d-1",
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
                "summary": "Good week",
                "highlights": ["Shipped feature X"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "d-1"
        assert data["summary"] == "Good week"
        assert data["highlights"] == ["Shipped feature X"]

    def test_list_digests_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/digests")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_digest_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digests",
            json={
                "id": "d-2",
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
                "summary": "Summary",
            },
        )
        resp = client.get("/api/v1/digests/d-2")
        assert resp.status_code == 200
        assert resp.json()["summary"] == "Summary"

    def test_get_digest_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/digests/nonexistent")
        assert resp.status_code == 404

    def test_delete_digest_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digests",
            json={
                "id": "d-3",
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
                "summary": "Bye",
            },
        )
        resp = client.delete("/api/v1/digests/d-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/digests/d-3").status_code == 404


class TestDigestConfigAPI:
    def test_create_config_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/digest-configs",
            json={
                "id": "dc-1",
                "project_id": "p-1",
                "schedule": "weekly",
                "recipients": ["alice@example.com"],
                "enabled": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "dc-1"
        assert data["schedule"] == "weekly"
        assert data["recipients"] == ["alice@example.com"]

    def test_list_configs_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/digest-configs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_config_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digest-configs",
            json={"id": "dc-2", "project_id": "p-1"},
        )
        resp = client.get("/api/v1/digest-configs/dc-2")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "p-1"

    def test_get_config_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/digest-configs/nonexistent")
        assert resp.status_code == 404

    def test_update_config(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digest-configs",
            json={"id": "dc-3", "project_id": "p-1", "schedule": "weekly"},
        )
        resp = client.patch(
            "/api/v1/digest-configs/dc-3",
            json={"schedule": "daily"},
        )
        assert resp.status_code == 200
        assert resp.json()["schedule"] == "daily"

    def test_update_config_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/digest-configs/nonexistent",
            json={"schedule": "daily"},
        )
        assert resp.status_code == 404

    def test_delete_config_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digest-configs",
            json={"id": "dc-4", "project_id": "p-1"},
        )
        resp = client.delete("/api/v1/digest-configs/dc-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/digest-configs/dc-4").status_code == 404

    def test_update_config_recipients(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digest-configs",
            json={"id": "dc-5", "project_id": "p-1", "recipients": ["a@b.com"]},
        )
        resp = client.patch(
            "/api/v1/digest-configs/dc-5",
            json={"recipients": ["x@y.com", "z@w.com"]},
        )
        assert resp.status_code == 200
        assert resp.json()["recipients"] == ["x@y.com", "z@w.com"]


class TestGenerateDigest:
    def test_generate_empty_activity(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/digests/generate",
            json={
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == "p-1"
        assert data["team_id"] == "t-1"
        assert data["metrics"]["work_items_completed"] == 0
        assert data["metrics"]["pipelines_succeeded"] == 0

    def test_generate_with_work_items(
        self,
        client: TestClient,
        wi_store: FakeWorkItemStore,
    ) -> None:
        wi_store.items = [
            {
                "project_id": "p-1",
                "status": "done",
                "updated_at": "2026-03-25T12:00:00Z",
                "title": "Fix bug",
            },
            {
                "project_id": "p-1",
                "status": "in_progress",
                "updated_at": "2026-03-26T12:00:00Z",
                "title": "New feature",
            },
            {
                "project_id": "p-1",
                "status": "done",
                "updated_at": "2026-03-20T12:00:00Z",
                "title": "Old item outside period",
            },
        ]
        resp = client.post(
            "/api/v1/digests/generate",
            json={
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["metrics"]["work_items_completed"] == 1
        assert data["metrics"]["work_items_in_progress"] == 1
        assert data["metrics"]["total_work_items"] == 2
        assert "1 work item(s) completed" in data["highlights"]

    def test_generate_with_pipelines(
        self,
        client: TestClient,
        pl_store: FakePipelineStore,
    ) -> None:
        pl_store.items = [
            {
                "project_id": "p-1",
                "status": "completed",
                "updated_at": "2026-03-25T12:00:00Z",
            },
            {
                "project_id": "p-1",
                "status": "failed",
                "updated_at": "2026-03-26T12:00:00Z",
            },
        ]
        resp = client.post(
            "/api/v1/digests/generate",
            json={
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["metrics"]["pipelines_succeeded"] == 1
        assert data["metrics"]["pipelines_failed"] == 1
        assert "1 pipeline(s) succeeded" in data["highlights"]
        assert "1 pipeline(s) failed" in data["highlights"]

    def test_generate_defaults_to_last_7_days(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/digests/generate",
            json={"project_id": "p-1", "team_id": "t-1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["period_start"] is not None
        assert data["period_end"] is not None

    def test_generate_stores_digest(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/digests/generate",
            json={
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
            },
        )
        digest_id = resp.json()["id"]
        get_resp = client.get(f"/api/v1/digests/{digest_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == digest_id
