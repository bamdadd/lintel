"""Tests for artifacts API."""

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


class TestArtifactsAPI:
    def test_create_artifact_returns_201(
        self, client: TestClient,
    ) -> None:
        resp = client.post("/api/v1/artifacts", json={
            "artifact_id": "art-1",
            "work_item_id": "wi-1",
            "run_id": "run-1",
            "artifact_type": "source",
            "path": "src/main.py",
            "content": "print('hello')",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["artifact_id"] == "art-1"
        assert data["path"] == "src/main.py"

    def test_list_artifacts_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/artifacts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_artifact_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/artifacts", json={
            "artifact_id": "art-2",
            "work_item_id": "wi-1",
            "run_id": "run-1",
            "artifact_type": "test",
        })
        resp = client.get("/api/v1/artifacts/art-2")
        assert resp.status_code == 200
        assert resp.json()["artifact_id"] == "art-2"

    def test_get_artifact_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/artifacts/nonexistent")
        assert resp.status_code == 404

    def test_create_test_result_returns_201(
        self, client: TestClient,
    ) -> None:
        resp = client.post("/api/v1/test-results", json={
            "result_id": "tr-1",
            "run_id": "run-1",
            "stage_id": "stage-1",
            "verdict": "passed",
            "total": 10,
            "passed": 10,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["result_id"] == "tr-1"
        assert data["verdict"] == "passed"

    def test_get_test_result_not_found(
        self, client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/test-results/nonexistent")
        assert resp.status_code == 404
