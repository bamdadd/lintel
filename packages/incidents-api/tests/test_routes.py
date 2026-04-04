"""Tests for incidents API."""

from fastapi.testclient import TestClient


class TestIncidentsFromAlert:
    def test_create_incident_from_alert_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/incidents/from-alert",
            json={
                "alert_text": "CRITICAL: service:payments is down",
                "project_id": "proj-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "critical"
        assert data["status"] == "detected"
        assert data["hotfix_branch"].startswith("hotfix/")
        assert "incident_id" in data

    def test_create_incident_default_severity(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/incidents/from-alert",
            json={
                "alert_text": "Something broke in production",
                "project_id": "proj-1",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["severity"] == "major"

    def test_create_incident_missing_alert_text(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/incidents/from-alert",
            json={"project_id": "proj-1", "alert_text": ""},
        )
        assert resp.status_code == 422

    def test_create_incident_missing_project_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/incidents/from-alert",
            json={"alert_text": "alert"},
        )
        assert resp.status_code == 422


class TestIncidentsList:
    def test_list_incidents_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/incidents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_incidents_after_create(self, client: TestClient) -> None:
        client.post(
            "/api/v1/incidents/from-alert",
            json={
                "alert_text": "MINOR: disk usage high",
                "project_id": "proj-1",
            },
        )
        resp = client.get("/api/v1/incidents")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_incident_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/incidents/nonexistent")
        assert resp.status_code == 404


class TestIncidentGet:
    def test_get_incident_by_id(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/incidents/from-alert",
            json={
                "alert_text": "WARNING: high latency on service:api-gateway",
                "project_id": "proj-2",
            },
        )
        incident_id = create_resp.json()["incident_id"]
        resp = client.get(f"/api/v1/incidents/{incident_id}")
        assert resp.status_code == 200
        assert resp.json()["incident_id"] == incident_id
