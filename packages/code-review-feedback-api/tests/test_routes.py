"""Tests for code review feedback API."""

from fastapi.testclient import TestClient


class TestReviewCommentAPI:
    def test_create_review_comment_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/review-comments",
            json={
                "id": "rc-1",
                "pipeline_run_id": "run-1",
                "file_path": "src/main.py",
                "line_number": 42,
                "comment": "Consider using a constant here",
                "severity": "warning",
                "suggestion": "MY_CONSTANT = 42",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "rc-1"
        assert data["pipeline_run_id"] == "run-1"
        assert data["file_path"] == "src/main.py"
        assert data["line_number"] == 42
        assert data["severity"] == "warning"
        assert data["status"] == "open"
        assert data["suggestion"] == "MY_CONSTANT = 42"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        payload = {
            "id": "rc-dup",
            "pipeline_run_id": "run-1",
            "file_path": "src/main.py",
            "line_number": 1,
            "comment": "duplicate test",
        }
        client.post("/api/v1/review-comments", json=payload)
        resp = client.post("/api/v1/review-comments", json=payload)
        assert resp.status_code == 409

    def test_create_invalid_severity_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/review-comments",
            json={
                "pipeline_run_id": "run-1",
                "file_path": "src/main.py",
                "line_number": 1,
                "comment": "test",
                "severity": "critical",
            },
        )
        assert resp.status_code == 400

    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/review-comments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_filter_by_pipeline_run_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/review-comments",
            json={
                "id": "rc-a",
                "pipeline_run_id": "run-1",
                "file_path": "a.py",
                "line_number": 1,
                "comment": "comment a",
            },
        )
        client.post(
            "/api/v1/review-comments",
            json={
                "id": "rc-b",
                "pipeline_run_id": "run-2",
                "file_path": "b.py",
                "line_number": 2,
                "comment": "comment b",
            },
        )
        resp = client.get("/api/v1/review-comments?pipeline_run_id=run-1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "rc-a"

    def test_get_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/review-comments",
            json={
                "id": "rc-get",
                "pipeline_run_id": "run-1",
                "file_path": "src/main.py",
                "line_number": 10,
                "comment": "test get",
            },
        )
        resp = client.get("/api/v1/review-comments/rc-get")
        assert resp.status_code == 200
        assert resp.json()["id"] == "rc-get"

    def test_get_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/review-comments/nonexistent")
        assert resp.status_code == 404

    def test_patch_resolve(self, client: TestClient) -> None:
        client.post(
            "/api/v1/review-comments",
            json={
                "id": "rc-resolve",
                "pipeline_run_id": "run-1",
                "file_path": "src/main.py",
                "line_number": 5,
                "comment": "fix this",
                "severity": "error",
            },
        )
        resp = client.patch(
            "/api/v1/review-comments/rc-resolve",
            json={"status": "resolved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_patch_dismiss(self, client: TestClient) -> None:
        client.post(
            "/api/v1/review-comments",
            json={
                "id": "rc-dismiss",
                "pipeline_run_id": "run-1",
                "file_path": "src/main.py",
                "line_number": 5,
                "comment": "nit",
            },
        )
        resp = client.patch(
            "/api/v1/review-comments/rc-dismiss",
            json={"status": "dismissed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dismissed"

    def test_patch_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/review-comments/nonexistent",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    def test_patch_invalid_status(self, client: TestClient) -> None:
        client.post(
            "/api/v1/review-comments",
            json={
                "id": "rc-bad-status",
                "pipeline_run_id": "run-1",
                "file_path": "src/main.py",
                "line_number": 1,
                "comment": "test",
            },
        )
        resp = client.patch(
            "/api/v1/review-comments/rc-bad-status",
            json={"status": "invalid"},
        )
        assert resp.status_code == 400

    def test_patch_update_comment_text(self, client: TestClient) -> None:
        client.post(
            "/api/v1/review-comments",
            json={
                "id": "rc-edit",
                "pipeline_run_id": "run-1",
                "file_path": "src/main.py",
                "line_number": 1,
                "comment": "original",
            },
        )
        resp = client.patch(
            "/api/v1/review-comments/rc-edit",
            json={"comment": "updated comment", "suggestion": "new suggestion"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["comment"] == "updated comment"
        assert data["suggestion"] == "new suggestion"
