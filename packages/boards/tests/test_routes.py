"""Tests for board and tag API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lintel.boards.routes import work_item_store_provider
from lintel.domain.types import WorkItem

if TYPE_CHECKING:
    from starlette.testclient import TestClient


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


class TestKanbanView:
    def _create_board(self, client: TestClient) -> dict[str, Any]:
        resp = client.post(
            "/api/v1/boards",
            json={
                "board_id": "b1",
                "project_id": "p1",
                "name": "Sprint Board",
                "columns": [
                    {
                        "column_id": "col-todo",
                        "name": "To Do",
                        "position": 0,
                        "work_item_status": "open",
                        "wip_limit": 5,
                    },
                    {
                        "column_id": "col-prog",
                        "name": "In Progress",
                        "position": 1,
                        "work_item_status": "in_progress",
                    },
                    {
                        "column_id": "col-done",
                        "name": "Done",
                        "position": 2,
                        "work_item_status": "closed",
                    },
                ],
            },
        )
        assert resp.status_code == 201
        return resp.json()

    async def _add_work_item(
        self,
        *,
        work_item_id: str,
        column_id: str,
        column_position: int = 0,
        tags: tuple[str, ...] = (),
    ) -> None:
        store = work_item_store_provider.get()
        wi = WorkItem(
            work_item_id=work_item_id,
            project_id="p1",
            title=f"Item {work_item_id}",
            column_id=column_id,
            column_position=column_position,
            tags=tags,
        )
        await store.add(wi)

    def test_kanban_empty_board(self, client: TestClient) -> None:
        self._create_board(client)
        resp = client.get("/api/v1/boards/b1/kanban")
        assert resp.status_code == 200
        data = resp.json()
        assert data["board_id"] == "b1"
        assert data["board_name"] == "Sprint Board"
        assert len(data["columns"]) == 3
        assert data["columns"][0]["name"] == "To Do"
        assert data["columns"][0]["work_items"] == []

    def test_kanban_items_grouped_by_column(self, client: TestClient) -> None:
        import asyncio

        self._create_board(client)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            self._add_work_item(
                work_item_id="w1",
                column_id="col-todo",
                column_position=0,
            )
        )
        loop.run_until_complete(
            self._add_work_item(
                work_item_id="w2",
                column_id="col-todo",
                column_position=1,
            )
        )
        loop.run_until_complete(
            self._add_work_item(
                work_item_id="w3",
                column_id="col-prog",
                column_position=0,
            )
        )

        resp = client.get("/api/v1/boards/b1/kanban")
        assert resp.status_code == 200
        data = resp.json()
        todo_col = data["columns"][0]
        assert len(todo_col["work_items"]) == 2
        assert todo_col["work_items"][0]["work_item_id"] == "w1"
        assert todo_col["work_items"][1]["work_item_id"] == "w2"

        prog_col = data["columns"][1]
        assert len(prog_col["work_items"]) == 1

        done_col = data["columns"][2]
        assert len(done_col["work_items"]) == 0

    def test_kanban_tag_filter(self, client: TestClient) -> None:
        import asyncio

        self._create_board(client)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            self._add_work_item(
                work_item_id="w1",
                column_id="col-todo",
                tags=("urgent",),
            )
        )
        loop.run_until_complete(
            self._add_work_item(
                work_item_id="w2",
                column_id="col-todo",
                tags=("low",),
            )
        )

        resp = client.get("/api/v1/boards/b1/kanban?tags=urgent")
        assert resp.status_code == 200
        data = resp.json()
        todo_items = data["columns"][0]["work_items"]
        assert len(todo_items) == 1
        assert todo_items[0]["work_item_id"] == "w1"

    def test_kanban_board_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/boards/nonexistent/kanban")
        assert resp.status_code == 404

    def test_kanban_wip_limit_in_response(self, client: TestClient) -> None:
        self._create_board(client)
        resp = client.get("/api/v1/boards/b1/kanban")
        data = resp.json()
        assert data["columns"][0]["wip_limit"] == 5
