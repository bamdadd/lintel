"""Tests for visual verification API routes."""

from fastapi.testclient import TestClient


def _create_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "vv-1",
        "pipeline_run_id": "run-1",
        "stage_name": "implement",
        "before_url": "https://img.example.com/before.png",
        "after_url": "https://img.example.com/after.png",
    }
    base.update(overrides)
    return base


class TestCreateVerification:
    def test_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/visual-verifications", json=_create_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "vv-1"
        assert data["pipeline_run_id"] == "run-1"
        assert data["stage_name"] == "implement"
        assert data["status"] == "pending"

    def test_duplicate_returns_409(self, client: TestClient) -> None:
        client.post("/api/v1/visual-verifications", json=_create_payload())
        resp = client.post("/api/v1/visual-verifications", json=_create_payload())
        assert resp.status_code == 409

    def test_auto_generates_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/visual-verifications",
            json={"pipeline_run_id": "run-x", "stage_name": "review"},
        )
        assert resp.status_code == 201
        assert resp.json()["id"]  # non-empty


class TestListVerifications:
    def test_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/visual-verifications")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_pipeline(self, client: TestClient) -> None:
        client.post(
            "/api/v1/visual-verifications",
            json=_create_payload(id="vv-a", pipeline_run_id="run-1"),
        )
        client.post(
            "/api/v1/visual-verifications",
            json=_create_payload(id="vv-b", pipeline_run_id="run-2"),
        )
        resp = client.get(
            "/api/v1/visual-verifications",
            params={"pipeline_run_id": "run-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["pipeline_run_id"] == "run-1"


class TestGetVerification:
    def test_found(self, client: TestClient) -> None:
        client.post("/api/v1/visual-verifications", json=_create_payload())
        resp = client.get("/api/v1/visual-verifications/vv-1")
        assert resp.status_code == 200
        assert resp.json()["stage_name"] == "implement"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/visual-verifications/nonexistent")
        assert resp.status_code == 404


class TestUpdateVerification:
    def test_update_status(self, client: TestClient) -> None:
        client.post("/api/v1/visual-verifications", json=_create_payload())
        resp = client.patch(
            "/api/v1/visual-verifications/vv-1",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_update_urls(self, client: TestClient) -> None:
        client.post("/api/v1/visual-verifications", json=_create_payload())
        resp = client.patch(
            "/api/v1/visual-verifications/vv-1",
            json={"diff_url": "https://img.example.com/diff.png"},
        )
        assert resp.status_code == 200
        assert resp.json()["diff_url"] == "https://img.example.com/diff.png"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/visual-verifications/nonexistent",
            json={"status": "rejected"},
        )
        assert resp.status_code == 404


class TestDeleteVerification:
    def test_returns_204(self, client: TestClient) -> None:
        client.post("/api/v1/visual-verifications", json=_create_payload())
        resp = client.delete("/api/v1/visual-verifications/vv-1")
        assert resp.status_code == 204
        assert client.get("/api/v1/visual-verifications/vv-1").status_code == 404

    def test_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/visual-verifications/nonexistent")
        assert resp.status_code == 404
