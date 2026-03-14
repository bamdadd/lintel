"""Tests for board and tag API endpoints."""

from __future__ import annotations

from typing import Any

from lintel.api.app import create_app
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client() -> TestClient:  # type: ignore[misc]
    with TestClient(create_app()) as c:
        yield c  # type: ignore[misc]


class TestTagCRUD:
    def test_create_and_get_tag(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/tags",
            json={"project_id": "p1", "name": "urgent", "color": "#ef4444"},
        )
        assert resp.status_code == 201
        tag = resp.json()
        assert tag["name"] == "urgent"
        assert tag["color"] == "#ef4444"

        get_resp = client.get(f"/api/v1/tags/{tag['tag_id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "urgent"

    def test_list_tags_by_project(self, client: TestClient) -> None:
        client.post("/api/v1/tags", json={"project_id": "p1", "name": "t1"})
        client.post("/api/v1/tags", json={"project_id": "p2", "name": "t2"})

        resp = client.get("/api/v1/projects/p1/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert len(tags) == 1
        assert tags[0]["name"] == "t1"

    def test_update_tag(self, client: TestClient) -> None:
        create = client.post("/api/v1/tags", json={"project_id": "p1", "name": "old"})
        tag_id = create.json()["tag_id"]

        resp = client.patch(f"/api/v1/tags/{tag_id}", json={"name": "new"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new"

    def test_delete_tag(self, client: TestClient) -> None:
        create = client.post("/api/v1/tags", json={"project_id": "p1", "name": "tmp"})
        tag_id = create.json()["tag_id"]

        resp = client.delete(f"/api/v1/tags/{tag_id}")
        assert resp.status_code == 204

        get_resp = client.get(f"/api/v1/tags/{tag_id}")
        assert get_resp.status_code == 404

    def test_tag_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tags/nonexistent")
        assert resp.status_code == 404

    def test_duplicate_tag(self, client: TestClient) -> None:
        body: dict[str, Any] = {"tag_id": "dup", "project_id": "p1", "name": "x"}
        client.post("/api/v1/tags", json=body)
        resp = client.post("/api/v1/tags", json=body)
        assert resp.status_code == 409


class TestBoardCRUD:
    def test_create_and_get_board(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/boards",
            json={
                "project_id": "p1",
                "name": "Sprint Board",
                "columns": [
                    {"name": "To Do", "position": 0, "work_item_status": "open"},
                    {"name": "Done", "position": 1, "work_item_status": "closed"},
                ],
            },
        )
        assert resp.status_code == 201
        board = resp.json()
        assert board["name"] == "Sprint Board"
        assert len(board["columns"]) == 2
        assert board["columns"][0]["name"] == "To Do"

        get_resp = client.get(f"/api/v1/boards/{board['board_id']}")
        assert get_resp.status_code == 200

    def test_list_boards_by_project(self, client: TestClient) -> None:
        client.post("/api/v1/boards", json={"project_id": "p1", "name": "B1"})
        client.post("/api/v1/boards", json={"project_id": "p2", "name": "B2"})

        resp = client.get("/api/v1/projects/p1/boards")
        assert resp.status_code == 200
        boards = resp.json()
        assert len(boards) == 1
        assert boards[0]["name"] == "B1"

    def test_update_board(self, client: TestClient) -> None:
        create = client.post("/api/v1/boards", json={"project_id": "p1", "name": "Old"})
        board_id = create.json()["board_id"]

        resp = client.patch(f"/api/v1/boards/{board_id}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_delete_board(self, client: TestClient) -> None:
        create = client.post("/api/v1/boards", json={"project_id": "p1", "name": "tmp"})
        board_id = create.json()["board_id"]

        resp = client.delete(f"/api/v1/boards/{board_id}")
        assert resp.status_code == 204

        get_resp = client.get(f"/api/v1/boards/{board_id}")
        assert get_resp.status_code == 404

    def test_board_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/boards/nonexistent")
        assert resp.status_code == 404
