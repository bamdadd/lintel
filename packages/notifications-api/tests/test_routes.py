"""Tests for notifications API."""

from fastapi.testclient import TestClient


class TestNotificationsAPI:
    def test_create_notification_rule_returns_201(
        self,
        client: TestClient,
    ) -> None:
        resp = client.post(
            "/api/v1/notifications/rules",
            json={
                "rule_id": "nr-1",
                "project_id": "proj-1",
                "event_types": ["deploy", "build"],
                "channel": "slack",
                "target": "#alerts",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_id"] == "nr-1"
        assert data["event_types"] == ["deploy", "build"]

    def test_list_notification_rules_empty(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/notifications/rules")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_notification_rule_by_id(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/notifications/rules",
            json={
                "rule_id": "nr-2",
                "project_id": "proj-1",
            },
        )
        resp = client.get("/api/v1/notifications/rules/nr-2")
        assert resp.status_code == 200
        assert resp.json()["rule_id"] == "nr-2"

    def test_get_notification_rule_not_found(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/notifications/rules/nonexistent")
        assert resp.status_code == 404

    def test_delete_notification_rule_returns_204(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/notifications/rules",
            json={
                "rule_id": "nr-3",
                "project_id": "proj-1",
            },
        )
        resp = client.delete("/api/v1/notifications/rules/nr-3")
        assert resp.status_code == 204
        resp = client.get("/api/v1/notifications/rules/nr-3")
        assert resp.status_code == 404
