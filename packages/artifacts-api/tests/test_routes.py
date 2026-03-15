"""Tests for artifacts API."""

from dataclasses import dataclass
from enum import Enum
import json

from fastapi.testclient import TestClient


class TestArtifactsAPI:
    def test_create_artifact_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/artifacts",
            json={
                "artifact_id": "art-1",
                "work_item_id": "wi-1",
                "run_id": "run-1",
                "artifact_type": "source",
                "path": "src/main.py",
                "content": "print('hello')",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["artifact_id"] == "art-1"
        assert data["path"] == "src/main.py"

    def test_list_artifacts_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/artifacts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_artifact_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/artifacts",
            json={
                "artifact_id": "art-2",
                "work_item_id": "wi-1",
                "run_id": "run-1",
                "artifact_type": "test",
            },
        )
        resp = client.get("/api/v1/artifacts/art-2")
        assert resp.status_code == 200
        assert resp.json()["artifact_id"] == "art-2"

    def test_get_artifact_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/artifacts/nonexistent")
        assert resp.status_code == 404

    def test_create_test_result_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/test-results",
            json={
                "result_id": "tr-1",
                "run_id": "run-1",
                "stage_id": "stage-1",
                "verdict": "passed",
                "total": 10,
                "passed": 10,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["result_id"] == "tr-1"
        assert data["verdict"] == "passed"

    def test_delete_artifact(self, client: TestClient) -> None:
        client.post(
            "/api/v1/artifacts",
            json={
                "artifact_id": "art-del",
                "work_item_id": "wi-1",
                "run_id": "run-1",
                "artifact_type": "source",
            },
        )
        resp = client.delete("/api/v1/artifacts/art-del")
        assert resp.status_code == 204
        assert client.get("/api/v1/artifacts/art-del").status_code == 404

    def test_delete_artifact_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/artifacts/nonexistent")
        assert resp.status_code == 404

    def test_delete_test_result(self, client: TestClient) -> None:
        client.post(
            "/api/v1/test-results",
            json={
                "result_id": "tr-del",
                "run_id": "run-1",
                "stage_id": "stage-1",
                "verdict": "passed",
                "total": 1,
                "passed": 1,
            },
        )
        resp = client.delete("/api/v1/test-results/tr-del")
        assert resp.status_code == 204
        assert client.get("/api/v1/test-results/tr-del").status_code == 404

    def test_delete_test_result_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/test-results/nonexistent")
        assert resp.status_code == 404

    def test_get_test_result_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/test-results/nonexistent")
        assert resp.status_code == 404


class _Status(Enum):
    succeeded = "succeeded"
    running = "running"


@dataclass
class _FakeRun:
    status: _Status


class TestStreamArtifacts:
    def test_stream_completes_when_no_pipeline(self, client: TestClient) -> None:
        """Stream ends immediately with 'complete' when pipeline not found."""
        with client.stream("GET", "/api/v1/artifacts/stream?run_id=missing") as resp:
            assert resp.status_code == 200
            lines = [ln for ln in resp.iter_lines() if ln.startswith("data:")]
        assert len(lines) == 1
        evt = json.loads(lines[0].removeprefix("data: "))
        assert evt["type"] == "complete"

    def test_stream_emits_artifacts_then_completes(
        self, client: TestClient, fake_pipeline_store: object
    ) -> None:
        """Artifacts created before stream starts are emitted, then complete."""
        store = fake_pipeline_store  # type: ignore[assignment]
        store._runs["run-s1"] = _FakeRun(status=_Status.succeeded)

        # Create an artifact first
        client.post(
            "/api/v1/artifacts",
            json={
                "artifact_id": "art-stream",
                "work_item_id": "wi-1",
                "run_id": "run-s1",
                "artifact_type": "diff",
                "content": "some diff",
            },
        )

        with client.stream("GET", "/api/v1/artifacts/stream?run_id=run-s1") as resp:
            lines = [ln for ln in resp.iter_lines() if ln.startswith("data:")]

        events = [json.loads(ln.removeprefix("data: ")) for ln in lines]
        types = [e["type"] for e in events]
        assert "artifact" in types
        assert types[-1] == "complete"
        art_evt = next(e for e in events if e["type"] == "artifact")
        assert art_evt["data"]["artifact_id"] == "art-stream"

    def test_stream_emits_test_results(
        self, client: TestClient, fake_pipeline_store: object
    ) -> None:
        store = fake_pipeline_store  # type: ignore[assignment]
        store._runs["run-s2"] = _FakeRun(status=_Status.succeeded)

        client.post(
            "/api/v1/test-results",
            json={
                "result_id": "tr-stream",
                "run_id": "run-s2",
                "stage_id": "stage-1",
                "verdict": "passed",
                "total": 5,
                "passed": 5,
            },
        )

        with client.stream("GET", "/api/v1/artifacts/stream?run_id=run-s2") as resp:
            lines = [ln for ln in resp.iter_lines() if ln.startswith("data:")]

        events = [json.loads(ln.removeprefix("data: ")) for ln in lines]
        types = [e["type"] for e in events]
        assert "test_result" in types
        assert types[-1] == "complete"
