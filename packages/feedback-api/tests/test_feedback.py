"""Tests for feedback API endpoints (REQ-025)."""

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


class TestFeedbackAPI:
    def test_create_feedback(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/feedback",
            json={
                "feedback_id": "fb-1",
                "project_id": "proj-1",
                "title": "Button is broken",
                "body": "The submit button does not work on mobile",
                "category": "bug",
                "priority": "high",
                "submitted_by": "user-1",
                "tags": ["mobile", "ui"],
                "technical_context": {
                    "browser": "Safari 17",
                    "device": "iPhone 15",
                    "url": "/settings",
                },
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["feedback_id"] == "fb-1"
        assert data["category"] == "bug"
        assert data["priority"] == "high"
        assert data["status"] == "new"
        assert data["technical_context"]["browser"] == "Safari 17"
        assert data["tags"] == ["mobile", "ui"]

    def test_create_feedback_duplicate(self, client: TestClient) -> None:
        _create_project(client)
        payload = {
            "feedback_id": "fb-dup",
            "project_id": "proj-1",
            "title": "Dup",
        }
        assert client.post("/api/v1/feedback", json=payload).status_code == 201
        assert client.post("/api/v1/feedback", json=payload).status_code == 409

    def test_list_feedback(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/feedback",
            json={"feedback_id": "fb-a", "project_id": "proj-1", "title": "A"},
        )
        client.post(
            "/api/v1/feedback",
            json={"feedback_id": "fb-b", "project_id": "proj-1", "title": "B"},
        )
        resp = client.get("/api/v1/feedback")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_list_feedback_by_project(self, client: TestClient) -> None:
        _create_project(client, "proj-x")
        _create_project(client, "proj-y")
        client.post(
            "/api/v1/feedback",
            json={"feedback_id": "fb-x", "project_id": "proj-x", "title": "X"},
        )
        client.post(
            "/api/v1/feedback",
            json={"feedback_id": "fb-y", "project_id": "proj-y", "title": "Y"},
        )
        resp = client.get("/api/v1/feedback", params={"project_id": "proj-x"})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["feedback_id"] == "fb-x"

    def test_get_feedback(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/feedback",
            json={"feedback_id": "fb-get", "project_id": "proj-1", "title": "Get me"},
        )
        resp = client.get("/api/v1/feedback/fb-get")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get me"

    def test_get_feedback_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/feedback/missing").status_code == 404

    def test_update_feedback_category(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/feedback",
            json={"feedback_id": "fb-cat", "project_id": "proj-1", "title": "Categorize"},
        )
        resp = client.patch(
            "/api/v1/feedback/fb-cat",
            json={"category": "feature_request", "status": "categorized"},
        )
        assert resp.status_code == 200
        assert resp.json()["category"] == "feature_request"
        assert resp.json()["status"] == "categorized"

    def test_update_feedback_work_item(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/feedback",
            json={"feedback_id": "fb-wi", "project_id": "proj-1", "title": "Link WI"},
        )
        resp = client.patch(
            "/api/v1/feedback/fb-wi",
            json={"work_item_id": "wi-123", "status": "work_item_created"},
        )
        assert resp.status_code == 200
        assert resp.json()["work_item_id"] == "wi-123"

    def test_update_feedback_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/feedback/missing", json={"title": "nope"})
        assert resp.status_code == 404

    def test_delete_feedback(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/feedback",
            json={"feedback_id": "fb-del", "project_id": "proj-1", "title": "Delete me"},
        )
        assert client.delete("/api/v1/feedback/fb-del").status_code == 204
        assert client.get("/api/v1/feedback/fb-del").status_code == 404

    def test_delete_feedback_not_found(self, client: TestClient) -> None:
        assert client.delete("/api/v1/feedback/missing").status_code == 404
