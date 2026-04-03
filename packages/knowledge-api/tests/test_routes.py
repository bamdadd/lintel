"""Tests for knowledge API routes."""

from fastapi.testclient import TestClient


class TestKnowledgeCRUD:
    def test_create_entry_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/knowledge",
            json={
                "id": "k-1",
                "project_id": "p-1",
                "title": "Architecture overview",
                "content": "The system uses event sourcing...",
                "source_type": "document",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "k-1"
        assert data["title"] == "Architecture overview"
        assert data["source_type"] == "document"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        payload = {"id": "k-dup", "project_id": "p-1", "title": "Dup"}
        client.post("/api/v1/knowledge", json=payload)
        resp = client.post("/api/v1/knowledge", json=payload)
        assert resp.status_code == 409

    def test_list_entries_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/knowledge")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_entries_filter_by_project(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge",
            json={"id": "k-1", "project_id": "p-1", "title": "A"},
        )
        client.post(
            "/api/v1/knowledge",
            json={"id": "k-2", "project_id": "p-2", "title": "B"},
        )
        resp = client.get("/api/v1/knowledge", params={"project_id": "p-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "k-1"

    def test_get_entry_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge",
            json={"id": "k-1", "project_id": "p-1", "title": "Test"},
        )
        resp = client.get("/api/v1/knowledge/k-1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test"

    def test_get_entry_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/knowledge/missing")
        assert resp.status_code == 404

    def test_update_entry(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge",
            json={"id": "k-1", "project_id": "p-1", "title": "Old"},
        )
        resp = client.patch(
            "/api/v1/knowledge/k-1",
            json={"title": "New title", "source_type": "code"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New title"
        assert data["source_type"] == "code"

    def test_update_entry_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/knowledge/missing", json={"title": "X"})
        assert resp.status_code == 404

    def test_delete_entry_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge",
            json={"id": "k-1", "project_id": "p-1", "title": "Bye"},
        )
        resp = client.delete("/api/v1/knowledge/k-1")
        assert resp.status_code == 204
        assert client.get("/api/v1/knowledge/k-1").status_code == 404

    def test_delete_entry_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/knowledge/missing")
        assert resp.status_code == 404


class TestKnowledgeSearch:
    def test_search_by_text_query(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge",
            json={
                "id": "k-1",
                "project_id": "p-1",
                "title": "Database schema",
                "content": "PostgreSQL tables for events",
            },
        )
        client.post(
            "/api/v1/knowledge",
            json={
                "id": "k-2",
                "project_id": "p-1",
                "title": "API design",
                "content": "REST endpoints for workflows",
            },
        )
        resp = client.post(
            "/api/v1/knowledge/search",
            json={"query": "database"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "k-1"

    def test_search_by_embedding(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge",
            json={
                "id": "k-1",
                "project_id": "p-1",
                "title": "Close match",
                "embedding": [1.0, 0.0, 0.0],
            },
        )
        client.post(
            "/api/v1/knowledge",
            json={
                "id": "k-2",
                "project_id": "p-1",
                "title": "Far match",
                "embedding": [0.0, 1.0, 0.0],
            },
        )
        resp = client.post(
            "/api/v1/knowledge/search",
            json={"query_embedding": [1.0, 0.0, 0.0]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == "k-1"
        assert "score" in data[0]
        assert data[0]["score"] > data[1]["score"]

    def test_search_filters_by_project(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge",
            json={
                "id": "k-1",
                "project_id": "p-1",
                "title": "Match",
                "content": "Relevant info",
            },
        )
        client.post(
            "/api/v1/knowledge",
            json={
                "id": "k-2",
                "project_id": "p-2",
                "title": "Also match",
                "content": "Relevant info",
            },
        )
        resp = client.post(
            "/api/v1/knowledge/search",
            json={"query": "relevant", "project_id": "p-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "p-1"

    def test_search_respects_limit(self, client: TestClient) -> None:
        for i in range(5):
            client.post(
                "/api/v1/knowledge",
                json={
                    "id": f"k-{i}",
                    "project_id": "p-1",
                    "title": f"Entry {i}",
                    "content": "common text",
                },
            )
        resp = client.post(
            "/api/v1/knowledge/search",
            json={"query": "common", "limit": 2},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2
