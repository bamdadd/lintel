"""Tests for scheduled tasks API."""

from fastapi.testclient import TestClient


class TestScheduledTasksAPI:
    def test_create_scheduled_task_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/scheduled-tasks",
            json={
                "id": "st-1",
                "project_id": "proj-1",
                "name": "Nightly Deps Update",
                "cron_expression": "0 0 * * *",
                "task_type": "dependency_update",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "st-1"
        assert data["name"] == "Nightly Deps Update"
        assert data["task_type"] == "dependency_update"
        assert data["enabled"] is True

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        payload = {
            "id": "st-dup",
            "project_id": "proj-1",
            "name": "Task",
            "cron_expression": "0 0 * * *",
            "task_type": "custom",
        }
        client.post("/api/v1/scheduled-tasks", json=payload)
        resp = client.post("/api/v1/scheduled-tasks", json=payload)
        assert resp.status_code == 409

    def test_list_scheduled_tasks_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/scheduled-tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_scheduled_tasks_with_project_filter(self, client: TestClient) -> None:
        client.post(
            "/api/v1/scheduled-tasks",
            json={
                "id": "st-a",
                "project_id": "proj-1",
                "name": "Task A",
                "cron_expression": "0 0 * * *",
                "task_type": "coverage_sweep",
            },
        )
        client.post(
            "/api/v1/scheduled-tasks",
            json={
                "id": "st-b",
                "project_id": "proj-2",
                "name": "Task B",
                "cron_expression": "0 0 * * *",
                "task_type": "security_scan",
            },
        )
        resp = client.get("/api/v1/scheduled-tasks", params={"project_id": "proj-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "proj-1"

    def test_get_scheduled_task_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/scheduled-tasks",
            json={
                "id": "st-2",
                "project_id": "proj-1",
                "name": "Coverage Sweep",
                "cron_expression": "0 2 * * 0",
                "task_type": "coverage_sweep",
            },
        )
        resp = client.get("/api/v1/scheduled-tasks/st-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Coverage Sweep"

    def test_get_scheduled_task_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/scheduled-tasks/nonexistent")
        assert resp.status_code == 404

    def test_update_scheduled_task(self, client: TestClient) -> None:
        client.post(
            "/api/v1/scheduled-tasks",
            json={
                "id": "st-3",
                "project_id": "proj-1",
                "name": "Old Name",
                "cron_expression": "0 0 * * *",
                "task_type": "custom",
            },
        )
        resp = client.patch(
            "/api/v1/scheduled-tasks/st-3",
            json={"name": "New Name", "enabled": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"
        assert data["enabled"] is False

    def test_update_scheduled_task_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/scheduled-tasks/nonexistent",
            json={"name": "Whatever"},
        )
        assert resp.status_code == 404

    def test_delete_scheduled_task_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/scheduled-tasks",
            json={
                "id": "st-4",
                "project_id": "proj-1",
                "name": "To Delete",
                "cron_expression": "0 0 * * *",
                "task_type": "security_scan",
            },
        )
        resp = client.delete("/api/v1/scheduled-tasks/st-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/scheduled-tasks/st-4").status_code == 404

    def test_delete_scheduled_task_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/scheduled-tasks/nonexistent")
        assert resp.status_code == 404
