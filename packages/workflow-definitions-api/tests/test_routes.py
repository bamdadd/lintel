"""Tests for the workflow definition API endpoints."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestWorkflowDefinitionAPI:
    def test_list_has_default_template(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflow-definitions")
        assert resp.status_code == 200
        data = resp.json()
        ids = [d["definition_id"] for d in data]
        assert "feature_to_pr" in ids

    def test_list_templates_returns_only_templates(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workflow-definitions",
            json={"definition_id": "custom", "name": "Custom", "is_template": False},
        )
        resp = client.get("/api/v1/workflow-definitions/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["is_template"] for d in data)
        ids = [d["definition_id"] for d in data]
        assert "feature_to_pr" in ids
        assert "custom" not in ids

    def test_get_builtin_has_graph_nodes_and_edges(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflow-definitions/feature_to_pr")
        assert resp.status_code == 200
        data = resp.json()
        assert "graph" in data
        assert len(data["graph"]["nodes"]) > 0
        assert len(data["graph"]["edges"]) > 0

    def test_get_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflow-definitions/nonexistent")
        assert resp.status_code == 404

    def test_create_workflow_definition(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/workflow-definitions",
            json={
                "definition_id": "my_flow",
                "name": "My Flow",
                "description": "A custom flow",
                "graph": {"nodes": ["a", "b"], "edges": [["a", "b"]]},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["definition_id"] == "my_flow"
        assert data["name"] == "My Flow"
        assert data["created_at"] is not None

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {"definition_id": "dup", "name": "Dup"}
        client.post("/api/v1/workflow-definitions", json=body)
        resp = client.post("/api/v1/workflow-definitions", json=body)
        assert resp.status_code == 409

    def test_update_graph_changes_updated_at(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workflow-definitions",
            json={"definition_id": "upd", "name": "Upd"},
        )
        original = client.get("/api/v1/workflow-definitions/upd").json()
        time.sleep(0.01)
        resp = client.put(
            "/api/v1/workflow-definitions/upd",
            json={"graph": {"nodes": ["x"], "edges": []}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["graph"]["nodes"] == ["x"]
        assert data["updated_at"] >= original["updated_at"]

    def test_delete_then_404(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workflow-definitions",
            json={"definition_id": "del_me", "name": "Del"},
        )
        resp = client.delete("/api/v1/workflow-definitions/del_me")
        assert resp.status_code == 204
        assert client.get("/api/v1/workflow-definitions/del_me").status_code == 404
