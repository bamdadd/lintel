"""Tests for release notes API."""

from fastapi.testclient import TestClient


def _create_note(client: TestClient, **overrides: object) -> dict:
    payload = {
        "id": "rn-1",
        "project_id": "proj-1",
        "version": "1.0.0",
        "title": "Release 1.0.0",
        "summary": "First release",
        "entries": [
            {
                "pr_number": 42,
                "title": "Add feature X",
                "category": "feature",
                "description": "Adds the X feature",
            },
        ],
        **overrides,
    }
    return client.post("/api/v1/release-notes", json=payload).json()


class TestReleaseNotesAPI:
    def test_create_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/release-notes",
            json={
                "id": "rn-1",
                "project_id": "proj-1",
                "version": "1.0.0",
                "title": "Release 1.0.0",
                "summary": "First release",
                "entries": [
                    {
                        "pr_number": 42,
                        "title": "Add feature X",
                        "category": "feature",
                        "description": "Adds the X feature",
                    },
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "rn-1"
        assert data["version"] == "1.0.0"
        assert len(data["entries"]) == 1
        assert data["entries"][0]["pr_number"] == 42
        assert data["published_at"] is None

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        _create_note(client, id="rn-dup")
        resp = client.post(
            "/api/v1/release-notes",
            json={
                "id": "rn-dup",
                "project_id": "proj-1",
                "version": "1.0.1",
                "title": "Dup",
                "summary": "Dup",
            },
        )
        assert resp.status_code == 409

    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/release-notes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        _create_note(client, id="rn-a")
        _create_note(client, id="rn-b", version="2.0.0")
        resp = client.get("/api/v1/release-notes")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_filter_by_project(self, client: TestClient) -> None:
        _create_note(client, id="rn-p1", project_id="proj-1")
        _create_note(client, id="rn-p2", project_id="proj-2")
        resp = client.get("/api/v1/release-notes", params={"project_id": "proj-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "proj-1"

    def test_get_by_id(self, client: TestClient) -> None:
        _create_note(client, id="rn-get")
        resp = client.get("/api/v1/release-notes/rn-get")
        assert resp.status_code == 200
        assert resp.json()["id"] == "rn-get"

    def test_get_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/release-notes/nonexistent")
        assert resp.status_code == 404

    def test_update_title(self, client: TestClient) -> None:
        _create_note(client, id="rn-upd")
        resp = client.patch(
            "/api/v1/release-notes/rn-upd",
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_entries(self, client: TestClient) -> None:
        _create_note(client, id="rn-ent")
        resp = client.patch(
            "/api/v1/release-notes/rn-ent",
            json={
                "entries": [
                    {
                        "pr_number": 99,
                        "title": "Fix bug",
                        "category": "bugfix",
                        "description": "Fixed a bug",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 1
        assert entries[0]["pr_number"] == 99

    def test_update_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/release-notes/nonexistent",
            json={"title": "x"},
        )
        assert resp.status_code == 404

    def test_delete_returns_204(self, client: TestClient) -> None:
        _create_note(client, id="rn-del")
        resp = client.delete("/api/v1/release-notes/rn-del")
        assert resp.status_code == 204
        assert client.get("/api/v1/release-notes/rn-del").status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/release-notes/nonexistent")
        assert resp.status_code == 404


class TestReleaseNoteStore:
    def test_list_by_project_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/release-notes", params={"project_id": "no-such"})
        assert resp.status_code == 200
        assert resp.json() == []
