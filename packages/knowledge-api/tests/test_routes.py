"""Tests for knowledge graph API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestKnowledgeAPI:
    def test_create_edge_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/knowledge/edges",
            json={
                "edge_id": "e-1",
                "from_id": "obs-1",
                "to_id": "obs-2",
                "edge_type": "inspired_by",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["edge_id"] == "e-1"
        assert data["edge_type"] == "inspired_by"

    def test_create_duplicate_edge_returns_409(self, client: TestClient) -> None:
        payload = {
            "edge_id": "e-dup1",
            "from_id": "obs-1",
            "to_id": "obs-2",
            "edge_type": "extends",
        }
        client.post("/api/v1/knowledge/edges", json=payload)
        payload["edge_id"] = "e-dup2"  # different id, same from/to/type
        resp = client.post("/api/v1/knowledge/edges", json=payload)
        assert resp.status_code == 409

    def test_get_edge(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge/edges",
            json={"edge_id": "e-get", "from_id": "a", "to_id": "b"},
        )
        resp = client.get("/api/v1/knowledge/edges/e-get")
        assert resp.status_code == 200
        assert resp.json()["edge_id"] == "e-get"

    def test_get_missing_edge_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/knowledge/edges/missing")
        assert resp.status_code == 404

    def test_graph_traversal(self, client: TestClient) -> None:
        # Create chain: A -> B -> C
        client.post(
            "/api/v1/knowledge/edges",
            json={"edge_id": "e1", "from_id": "A", "to_id": "B"},
        )
        client.post(
            "/api/v1/knowledge/edges",
            json={"edge_id": "e2", "from_id": "B", "to_id": "C"},
        )
        resp = client.get("/api/v1/knowledge/graph", params={"root_id": "A"})
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["node_ids"]) == {"A", "B", "C"}
        assert len(data["edges"]) == 2

    def test_graph_cycle_detection(self, client: TestClient) -> None:
        # Create cycle: X -> Y -> X (different edge types to avoid dup)
        client.post(
            "/api/v1/knowledge/edges",
            json={"edge_id": "ec1", "from_id": "X", "to_id": "Y", "edge_type": "inspired_by"},
        )
        client.post(
            "/api/v1/knowledge/edges",
            json={"edge_id": "ec2", "from_id": "Y", "to_id": "X", "edge_type": "extends"},
        )
        resp = client.get("/api/v1/knowledge/graph", params={"root_id": "X"})
        assert resp.status_code == 200
        data = resp.json()
        # Should not infinite loop - visited set prevents it
        assert set(data["node_ids"]) == {"X", "Y"}

    def test_graph_max_depth(self, client: TestClient) -> None:
        # Create chain: D1 -> D2 -> D3 -> D4
        for i in range(1, 4):
            client.post(
                "/api/v1/knowledge/edges",
                json={
                    "edge_id": f"ed{i}",
                    "from_id": f"D{i}",
                    "to_id": f"D{i + 1}",
                    "edge_type": "extends",
                },
            )
        resp = client.get(
            "/api/v1/knowledge/graph",
            params={"root_id": "D1", "max_depth": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only depth 1: D1 -> D2
        assert "D3" not in data["node_ids"]
