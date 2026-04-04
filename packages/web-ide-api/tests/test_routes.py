"""Tests for Web IDE API."""

from fastapi.testclient import TestClient


class TestIDESessionCRUD:
    def test_create_session_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ide/sessions",
            json={
                "session_id": "ide-1",
                "sandbox_id": "sbx-1",
                "project_id": "proj-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["session_id"] == "ide-1"
        assert data["sandbox_id"] == "sbx-1"
        assert data["status"] == "starting"
        assert data["proxy_url"] == "/ide/sessions/ide-1/proxy"

    def test_create_session_conflict(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ide/sessions",
            json={"session_id": "ide-dup", "sandbox_id": "sbx-1", "project_id": "proj-1"},
        )
        resp = client.post(
            "/api/v1/ide/sessions",
            json={"session_id": "ide-dup", "sandbox_id": "sbx-2", "project_id": "proj-1"},
        )
        assert resp.status_code == 409

    def test_list_sessions_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ide/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions_filter_by_project(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ide/sessions",
            json={"session_id": "ide-a", "sandbox_id": "sbx-1", "project_id": "proj-1"},
        )
        client.post(
            "/api/v1/ide/sessions",
            json={"session_id": "ide-b", "sandbox_id": "sbx-2", "project_id": "proj-2"},
        )
        resp = client.get("/api/v1/ide/sessions?project_id=proj-1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["session_id"] == "ide-a"

    def test_get_session_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ide/sessions",
            json={"session_id": "ide-2", "sandbox_id": "sbx-1", "project_id": "proj-1"},
        )
        resp = client.get("/api/v1/ide/sessions/ide-2")
        assert resp.status_code == 200
        assert resp.json()["sandbox_id"] == "sbx-1"

    def test_get_session_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ide/sessions/nonexistent")
        assert resp.status_code == 404

    def test_update_session_status(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ide/sessions",
            json={"session_id": "ide-3", "sandbox_id": "sbx-1", "project_id": "proj-1"},
        )
        resp = client.patch(
            "/api/v1/ide/sessions/ide-3",
            json={"status": "running"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_update_session_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/ide/sessions/nonexistent",
            json={"status": "running"},
        )
        assert resp.status_code == 404

    def test_delete_session_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ide/sessions",
            json={"session_id": "ide-4", "sandbox_id": "sbx-1", "project_id": "proj-1"},
        )
        resp = client.delete("/api/v1/ide/sessions/ide-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/ide/sessions/ide-4").status_code == 404

    def test_delete_session_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/ide/sessions/nonexistent")
        assert resp.status_code == 404

    def test_create_session_with_custom_port(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ide/sessions",
            json={
                "session_id": "ide-5",
                "sandbox_id": "sbx-1",
                "project_id": "proj-1",
                "port": 9090,
                "workspace_path": "/home/coder",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["port"] == 9090
        assert data["workspace_path"] == "/home/coder"
