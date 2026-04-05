"""Tests for browser extension modification API routes."""

from fastapi.testclient import TestClient


def _create_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "mod-1",
        "project_id": "proj-1",
        "component_path": "src/components/Header.tsx",
        "instructions": "Change the background color to blue",
        "screenshot_url": "https://img.example.com/screenshot.png",
        "selector": "div.header",
        "page_url": "http://localhost:3000/",
    }
    base.update(overrides)
    return base


class TestCreateModification:
    def test_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/browser-extension/modifications", json=_create_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "mod-1"
        assert data["project_id"] == "proj-1"
        assert data["component_path"] == "src/components/Header.tsx"
        assert data["instructions"] == "Change the background color to blue"
        assert data["status"] == "pending"

    def test_duplicate_returns_409(self, client: TestClient) -> None:
        client.post("/api/v1/browser-extension/modifications", json=_create_payload())
        resp = client.post("/api/v1/browser-extension/modifications", json=_create_payload())
        assert resp.status_code == 409

    def test_auto_generates_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/browser-extension/modifications",
            json={
                "project_id": "proj-x",
                "component_path": "src/App.tsx",
                "instructions": "Add a footer",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["id"]  # non-empty

    def test_minimal_required_fields(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/browser-extension/modifications",
            json={
                "project_id": "proj-1",
                "component_path": "src/App.tsx",
                "instructions": "Make it dark mode",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["screenshot_url"] == ""
        assert data["selector"] == ""
        assert data["page_url"] == ""


class TestListModifications:
    def test_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/browser-extension/modifications")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_project(self, client: TestClient) -> None:
        client.post(
            "/api/v1/browser-extension/modifications",
            json=_create_payload(id="mod-a", project_id="proj-1"),
        )
        client.post(
            "/api/v1/browser-extension/modifications",
            json=_create_payload(id="mod-b", project_id="proj-2"),
        )
        resp = client.get(
            "/api/v1/browser-extension/modifications",
            params={"project_id": "proj-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "proj-1"


class TestGetModification:
    def test_found(self, client: TestClient) -> None:
        client.post("/api/v1/browser-extension/modifications", json=_create_payload())
        resp = client.get("/api/v1/browser-extension/modifications/mod-1")
        assert resp.status_code == 200
        assert resp.json()["component_path"] == "src/components/Header.tsx"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/browser-extension/modifications/nonexistent")
        assert resp.status_code == 404


class TestUpdateModification:
    def test_update_status(self, client: TestClient) -> None:
        client.post("/api/v1/browser-extension/modifications", json=_create_payload())
        resp = client.patch(
            "/api/v1/browser-extension/modifications/mod-1",
            json={"status": "processing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    def test_update_preview(self, client: TestClient) -> None:
        client.post("/api/v1/browser-extension/modifications", json=_create_payload())
        resp = client.patch(
            "/api/v1/browser-extension/modifications/mod-1",
            json={
                "status": "preview_ready",
                "preview_url": "https://img.example.com/preview.png",
                "diff": "- color: red\n+ color: blue",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "preview_ready"
        assert data["preview_url"] == "https://img.example.com/preview.png"
        assert data["diff"] == "- color: red\n+ color: blue"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/browser-extension/modifications/nonexistent",
            json={"status": "failed"},
        )
        assert resp.status_code == 404


class TestDeleteModification:
    def test_returns_204(self, client: TestClient) -> None:
        client.post("/api/v1/browser-extension/modifications", json=_create_payload())
        resp = client.delete("/api/v1/browser-extension/modifications/mod-1")
        assert resp.status_code == 204
        assert client.get("/api/v1/browser-extension/modifications/mod-1").status_code == 404

    def test_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/browser-extension/modifications/nonexistent")
        assert resp.status_code == 404
