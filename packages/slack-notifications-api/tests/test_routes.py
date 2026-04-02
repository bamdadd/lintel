"""Tests for slack notifications API."""

from fastapi.testclient import TestClient


class TestTemplatesAPI:
    def test_create_template_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack/notification-templates",
            json={
                "template_id": "t-1",
                "name": "Research Complete",
                "stage_name": "research",
                "block_kit_template": '{"blocks":[]}',
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["template_id"] == "t-1"
        assert data["name"] == "Research Complete"
        assert data["stage_name"] == "research"
        assert data["active"] is True

    def test_list_templates_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack/notification-templates")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_template_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack/notification-templates",
            json={"template_id": "t-2", "name": "Impl Done", "stage_name": "implement"},
        )
        resp = client.get("/api/v1/slack/notification-templates/t-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Impl Done"

    def test_get_template_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack/notification-templates/nonexistent")
        assert resp.status_code == 404

    def test_update_template(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack/notification-templates",
            json={"template_id": "t-3", "name": "Old", "stage_name": "test"},
        )
        resp = client.patch(
            "/api/v1/slack/notification-templates/t-3",
            json={"name": "New"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_delete_template_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack/notification-templates",
            json={"template_id": "t-4", "name": "Del", "stage_name": "review"},
        )
        resp = client.delete("/api/v1/slack/notification-templates/t-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/slack/notification-templates/t-4").status_code == 404


class TestRecordsAPI:
    def test_list_records_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack/notification-records")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_records_filter_by_pipeline(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack/notify",
            json={
                "pipeline_run_id": "run-1",
                "stage_name": "research",
                "slack_channel_id": "C123",
                "slack_thread_ts": "1234.5678",
            },
        )
        resp = client.get("/api/v1/slack/notification-records?pipeline_run_id=run-1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestNotifyAPI:
    def test_notify_creates_record(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack/notify",
            json={
                "pipeline_run_id": "run-2",
                "stage_name": "implement",
                "slack_channel_id": "C456",
                "slack_thread_ts": "9999.0000",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["pipeline_run_id"] == "run-2"
        assert data["stage_name"] == "implement"
        assert data["status"] == "sent"
