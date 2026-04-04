"""Tests for Jira adapter API."""

from fastapi.testclient import TestClient


class TestJiraConnect:
    def test_connect_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/jira/connect",
            json={
                "connection_id": "conn-1",
                "project_id": "proj-1",
                "jira_base_url": "https://example.atlassian.net",
                "jira_project_key": "EX",
                "jira_email": "user@example.com",
                "api_token": "secret-token",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["connection_id"] == "conn-1"
        assert data["jira_project_key"] == "EX"
        assert "api_token" not in data

    def test_connect_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "connection_id": "conn-dup",
            "project_id": "proj-1",
            "jira_base_url": "https://example.atlassian.net",
            "jira_project_key": "EX",
            "jira_email": "user@example.com",
            "api_token": "secret",
        }
        client.post("/api/v1/integrations/jira/connect", json=body)
        resp = client.post("/api/v1/integrations/jira/connect", json=body)
        assert resp.status_code == 409


class TestJiraSync:
    def test_sync_unknown_connection_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/jira/sync",
            json={"connection_id": "nonexistent"},
        )
        assert resp.status_code == 404


class TestJiraWebhook:
    def test_webhook_no_match_returns_ignored(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integrations/jira/webhook",
            json={
                "webhookEvent": "jira:issue_updated",
                "issue": {"key": "UNKNOWN-1"},
                "changelog": {},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_webhook_matched_connection(self, client: TestClient) -> None:
        client.post(
            "/api/v1/integrations/jira/connect",
            json={
                "connection_id": "conn-wh",
                "project_id": "proj-1",
                "jira_base_url": "https://example.atlassian.net",
                "jira_project_key": "EX",
                "jira_email": "user@example.com",
                "api_token": "secret",
            },
        )
        resp = client.post(
            "/api/v1/integrations/jira/webhook",
            json={
                "webhookEvent": "jira:issue_created",
                "issue": {"key": "EX-42"},
                "changelog": {},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["issue_key"] == "EX-42"
