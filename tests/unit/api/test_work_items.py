"""Tests for work items API."""

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_work_item(
    client: TestClient,
    work_item_id: str = "wi1",
) -> dict:
    return client.post(
        "/api/v1/work-items",
        json={
            "work_item_id": work_item_id,
            "project_id": "proj-1",
            "title": "Fix bug",
        },
    ).json()


class TestWorkItemsAPI:
    def test_create_work_item(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/work-items",
            json={
                "work_item_id": "wi1",
                "project_id": "proj-1",
                "title": "Do something",
                "description": "Details here",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["work_item_id"] == "wi1"
        assert data["project_id"] == "proj-1"
        assert data["title"] == "Do something"
        assert data["status"] == "open"

    def test_create_work_item_duplicate_returns_409(
        self,
        client: TestClient,
    ) -> None:
        _create_work_item(client, "dup")
        resp = client.post(
            "/api/v1/work-items",
            json={
                "work_item_id": "dup",
                "project_id": "p",
                "title": "Again",
            },
        )
        assert resp.status_code == 409

    def test_list_work_items_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/work-items")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_work_items_with_items(self, client: TestClient) -> None:
        _create_work_item(client, "a")
        _create_work_item(client, "b")
        resp = client.get("/api/v1/work-items")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_work_item_by_id(self, client: TestClient) -> None:
        _create_work_item(client, "wi1")
        resp = client.get("/api/v1/work-items/wi1")
        assert resp.status_code == 200
        assert resp.json()["work_item_id"] == "wi1"

    def test_get_work_item_not_found_returns_404(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/work-items/missing")
        assert resp.status_code == 404

    def test_update_work_item(self, client: TestClient) -> None:
        _create_work_item(client, "wi1")
        resp = client.patch(
            "/api/v1/work-items/wi1",
            json={"title": "Updated title", "status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated title"
        assert resp.json()["status"] == "in_progress"

    def test_delete_work_item(self, client: TestClient) -> None:
        _create_work_item(client, "wi1")
        resp = client.delete("/api/v1/work-items/wi1")
        assert resp.status_code == 204
        assert client.get("/api/v1/work-items/wi1").status_code == 404
