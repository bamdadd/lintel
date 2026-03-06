"""Tests for pipelines API."""

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


def _create_pipeline(
    client: TestClient,
    run_id: str = "run1",
) -> dict:
    return client.post(
        "/api/v1/pipelines",
        json={
            "run_id": run_id,
            "project_id": "proj-1",
            "work_item_id": "wi-1",
        },
    ).json()


class TestPipelinesAPI:
    def test_create_pipeline(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/pipelines",
            json={
                "run_id": "run1",
                "project_id": "proj-1",
                "work_item_id": "wi-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["run_id"] == "run1"
        assert data["project_id"] == "proj-1"
        assert data["status"] == "pending"
        assert len(data["stages"]) == 8

    def test_create_pipeline_duplicate_returns_409(
        self,
        client: TestClient,
    ) -> None:
        _create_pipeline(client, "dup")
        resp = client.post(
            "/api/v1/pipelines",
            json={
                "run_id": "dup",
                "project_id": "p",
                "work_item_id": "w",
            },
        )
        assert resp.status_code == 409

    def test_list_pipelines_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/pipelines")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_pipelines_with_items(self, client: TestClient) -> None:
        _create_pipeline(client, "a")
        _create_pipeline(client, "b")
        resp = client.get("/api/v1/pipelines")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_pipeline_by_id(self, client: TestClient) -> None:
        _create_pipeline(client, "run1")
        resp = client.get("/api/v1/pipelines/run1")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run1"

    def test_get_pipeline_not_found_returns_404(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/pipelines/missing")
        assert resp.status_code == 404

    def test_cancel_pipeline(self, client: TestClient) -> None:
        _create_pipeline(client, "run1")
        resp = client.post("/api/v1/pipelines/run1/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        skipped = [s for s in data["stages"] if s["status"] == "skipped"]
        assert len(skipped) == 8

    def test_delete_pipeline(self, client: TestClient) -> None:
        _create_pipeline(client, "run1")
        resp = client.delete("/api/v1/pipelines/run1")
        assert resp.status_code == 204
        assert client.get("/api/v1/pipelines/run1").status_code == 404
