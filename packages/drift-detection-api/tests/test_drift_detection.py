"""Tests for drift detection API endpoints (rules, alerts, scans)."""

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


def _create_project(client: TestClient, project_id: str = "proj-1") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Test Project"},
    )
    assert resp.status_code == 201
    return resp.json()


# ======================== DRIFT RULES ========================


class TestDriftRulesAPI:
    def test_create_drift_rule(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/drift-rules",
            json={
                "rule_id": "rule-1",
                "project_id": "proj-1",
                "name": "Spec vs Code",
                "drift_type": "spec_not_reflected_in_plan",
                "severity": "high",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Spec vs Code"
        assert data["drift_type"] == "spec_not_reflected_in_plan"
        assert data["severity"] == "high"

    def test_list_drift_rules(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/drift-rules",
            json={"rule_id": "rule-1", "project_id": "proj-1", "name": "Rule 1"},
        )
        client.post(
            "/api/v1/drift-rules",
            json={"rule_id": "rule-2", "project_id": "proj-1", "name": "Rule 2"},
        )
        resp = client.get("/api/v1/drift-rules")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_drift_rule(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/drift-rules",
            json={"rule_id": "rule-1", "project_id": "proj-1", "name": "Old Name"},
        )
        resp = client.patch("/api/v1/drift-rules/rule-1", json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_drift_rule(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/drift-rules",
            json={"rule_id": "rule-1", "project_id": "proj-1", "name": "Delete Me"},
        )
        assert client.delete("/api/v1/drift-rules/rule-1").status_code == 204

    def test_get_drift_rule_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/drift-rules/nonexistent").status_code == 404

    def test_create_duplicate_drift_rule(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/drift-rules",
            json={"rule_id": "rule-1", "project_id": "proj-1", "name": "Rule"},
        )
        resp = client.post(
            "/api/v1/drift-rules",
            json={"rule_id": "rule-1", "project_id": "proj-1", "name": "Rule"},
        )
        assert resp.status_code == 409


# ======================== DRIFT ALERTS ========================


class TestDriftAlertsAPI:
    def test_create_drift_alert(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/drift-alerts",
            json={
                "alert_id": "alert-1",
                "project_id": "proj-1",
                "rule_id": "rule-1",
                "title": "Architecture out of sync",
                "severity": "critical",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Architecture out of sync"
        assert data["severity"] == "critical"
        assert data["status"] == "open"

    def test_update_alert_to_resolved(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/drift-alerts",
            json={
                "alert_id": "alert-1",
                "project_id": "proj-1",
                "rule_id": "rule-1",
                "title": "Drift",
            },
        )
        resp = client.patch("/api/v1/drift-alerts/alert-1", json={"status": "resolved"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_delete_drift_alert(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/drift-alerts",
            json={"alert_id": "alert-1", "project_id": "proj-1", "rule_id": "rule-1"},
        )
        assert client.delete("/api/v1/drift-alerts/alert-1").status_code == 204

    def test_list_alerts_by_project(self, client: TestClient) -> None:
        _create_project(client)
        _create_project(client, "proj-2")
        client.post(
            "/api/v1/drift-alerts",
            json={"alert_id": "a1", "project_id": "proj-1", "rule_id": "r1"},
        )
        client.post(
            "/api/v1/drift-alerts",
            json={"alert_id": "a2", "project_id": "proj-2", "rule_id": "r1"},
        )
        resp = client.get("/api/v1/drift-alerts", params={"project_id": "proj-1"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ======================== DRIFT SCANS ========================


class TestDriftScansAPI:
    def test_create_drift_scan(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/drift-scans",
            json={
                "scan_id": "scan-1",
                "project_id": "proj-1",
                "trigger": "webhook",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["trigger"] == "webhook"

    def test_update_scan_to_completed(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/drift-scans",
            json={"scan_id": "scan-1", "project_id": "proj-1"},
        )
        resp = client.patch(
            "/api/v1/drift-scans/scan-1",
            json={"status": "completed", "alerts_found": 3},
        )
        assert resp.status_code == 200
        assert resp.json()["alerts_found"] == 3

    def test_delete_drift_scan(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/drift-scans",
            json={"scan_id": "scan-1", "project_id": "proj-1"},
        )
        assert client.delete("/api/v1/drift-scans/scan-1").status_code == 204

    def test_get_scan_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/drift-scans/nonexistent").status_code == 404
