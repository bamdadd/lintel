"""Tests for automations API."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _automation_body(
    automation_id: str = "a-1",
    name: str = "Nightly Review",
    trigger_type: str = "cron",
) -> dict:
    return {
        "automation_id": automation_id,
        "project_id": "proj-1",
        "workflow_definition_id": "wf-1",
        "name": name,
        "trigger_type": trigger_type,
        "trigger_config": {"schedule": "0 2 * * *", "timezone": "UTC"},
    }


class TestAutomationsAPI:
    def test_create_automation_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/automations", json=_automation_body())
        assert resp.status_code == 201
        data = resp.json()
        assert data["automation_id"] == "a-1"
        assert data["name"] == "Nightly Review"
        assert data["enabled"] is True
        assert data["concurrency_policy"] == "queue"
        assert data["max_chain_depth"] == 3
        assert data["created_at"] != ""

    def test_list_automations_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/automations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_automation_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-2"))
        resp = client.get("/api/v1/automations/a-2")
        assert resp.status_code == 200
        assert resp.json()["automation_id"] == "a-2"

    def test_get_automation_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/automations/nonexistent")
        assert resp.status_code == 404

    def test_update_automation(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-3"))
        resp = client.patch(
            "/api/v1/automations/a-3",
            json={"name": "Updated", "concurrency_policy": "skip"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["concurrency_policy"] == "skip"

    def test_delete_automation_returns_204(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-4"))
        resp = client.delete("/api/v1/automations/a-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/automations/a-4").status_code == 404

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = _automation_body("a-dup")
        client.post("/api/v1/automations", json=body)
        resp = client.post("/api/v1/automations", json=body)
        assert resp.status_code == 409

    def test_list_filter_by_project(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-5"))
        resp = client.get("/api/v1/automations?project_id=proj-1")
        assert len(resp.json()) == 1
        resp2 = client.get("/api/v1/automations?project_id=other")
        assert len(resp2.json()) == 0

    def test_manual_trigger_returns_200(self, client: TestClient) -> None:
        body = _automation_body("a-6", trigger_type="manual")
        client.post("/api/v1/automations", json=body)
        resp = client.post("/api/v1/automations/a-6/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_run_id" in data

    def test_trigger_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/automations/nonexistent/trigger")
        assert resp.status_code == 404

    def test_trigger_disabled_returns_409(self, client: TestClient) -> None:
        body = _automation_body("a-7", trigger_type="manual")
        body["enabled"] = False
        client.post("/api/v1/automations", json=body)
        resp = client.post("/api/v1/automations/a-7/trigger")
        assert resp.status_code == 409

    def test_list_runs_empty(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-8"))
        resp = client.get("/api/v1/automations/a-8/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_runs_after_trigger(self, client: TestClient) -> None:
        body = _automation_body("a-9", trigger_type="manual")
        client.post("/api/v1/automations", json=body)
        client.post("/api/v1/automations/a-9/trigger")
        resp = client.get("/api/v1/automations/a-9/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
