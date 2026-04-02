"""Tests for context attachments API endpoints (REQ-027)."""

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


class TestContextAttachmentsAPI:
    def test_create_attachment(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/attachments",
            json={
                "attachment_id": "att-1",
                "project_id": "proj-1",
                "target_type": "work_item",
                "target_id": "wi-1",
                "attachment_type": "document",
                "filename": "spec.md",
                "url": "https://example.com/spec.md",
                "description": "Feature specification",
                "mime_type": "text/markdown",
                "size_bytes": 4096,
                "tags": ["spec", "feature"],
                "created_by": "user-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["attachment_id"] == "att-1"
        assert data["attachment_type"] == "document"
        assert data["filename"] == "spec.md"
        assert data["tags"] == ["spec", "feature"]
        assert data["target_type"] == "work_item"
        assert data["target_id"] == "wi-1"

    def test_create_attachment_duplicate(self, client: TestClient) -> None:
        _create_project(client)
        payload = {
            "attachment_id": "att-dup",
            "project_id": "proj-1",
            "filename": "dup.txt",
        }
        assert client.post("/api/v1/attachments", json=payload).status_code == 201
        assert client.post("/api/v1/attachments", json=payload).status_code == 409

    def test_list_attachments(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/attachments",
            json={"attachment_id": "att-a", "project_id": "proj-1", "filename": "a.txt"},
        )
        client.post(
            "/api/v1/attachments",
            json={"attachment_id": "att-b", "project_id": "proj-1", "filename": "b.txt"},
        )
        resp = client.get("/api/v1/attachments")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_list_attachments_by_project(self, client: TestClient) -> None:
        _create_project(client, "proj-x")
        _create_project(client, "proj-y")
        client.post(
            "/api/v1/attachments",
            json={"attachment_id": "att-x", "project_id": "proj-x", "filename": "x.txt"},
        )
        client.post(
            "/api/v1/attachments",
            json={"attachment_id": "att-y", "project_id": "proj-y", "filename": "y.txt"},
        )
        resp = client.get("/api/v1/attachments", params={"project_id": "proj-x"})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["attachment_id"] == "att-x"

    def test_list_attachments_by_target(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/attachments",
            json={
                "attachment_id": "att-t1",
                "project_id": "proj-1",
                "target_type": "work_item",
                "target_id": "wi-99",
                "filename": "t1.txt",
            },
        )
        client.post(
            "/api/v1/attachments",
            json={
                "attachment_id": "att-t2",
                "project_id": "proj-1",
                "target_type": "thread",
                "target_id": "th-1",
                "filename": "t2.txt",
            },
        )
        resp = client.get(
            "/api/v1/attachments",
            params={"target_type": "work_item", "target_id": "wi-99"},
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["attachment_id"] == "att-t1"

    def test_get_attachment(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/attachments",
            json={
                "attachment_id": "att-get",
                "project_id": "proj-1",
                "filename": "get.txt",
            },
        )
        resp = client.get("/api/v1/attachments/att-get")
        assert resp.status_code == 200
        assert resp.json()["filename"] == "get.txt"

    def test_get_attachment_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/attachments/missing").status_code == 404

    def test_update_attachment(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/attachments",
            json={
                "attachment_id": "att-upd",
                "project_id": "proj-1",
                "filename": "old.txt",
                "description": "old desc",
            },
        )
        resp = client.patch(
            "/api/v1/attachments/att-upd",
            json={"description": "new desc", "tags": ["updated"]},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "new desc"
        assert resp.json()["tags"] == ["updated"]

    def test_update_attachment_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/attachments/missing", json={"description": "nope"})
        assert resp.status_code == 404

    def test_delete_attachment(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/attachments",
            json={
                "attachment_id": "att-del",
                "project_id": "proj-1",
                "filename": "del.txt",
            },
        )
        assert client.delete("/api/v1/attachments/att-del").status_code == 204
        assert client.get("/api/v1/attachments/att-del").status_code == 404

    def test_delete_attachment_not_found(self, client: TestClient) -> None:
        assert client.delete("/api/v1/attachments/missing").status_code == 404
