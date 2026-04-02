"""Tests for workflow blueprints API endpoints."""

from typing import TYPE_CHECKING, Any

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_blueprint(
    client: TestClient,
    name: str = "my-blueprint",
    nodes: list[dict[str, Any]] | None = None,
    team_id: str = "team-1",
    active: bool = True,
) -> dict[str, Any]:
    if nodes is None:
        nodes = [
            {
                "name": "lint",
                "node_type": "deterministic",
                "description": "Run linter",
                "timeout_seconds": 60,
            },
            {
                "name": "implement",
                "node_type": "agentic",
                "description": "AI implements feature",
                "depends_on": [],
            },
        ]
    resp = client.post(
        "/api/v1/workflow-blueprints",
        json={
            "name": name,
            "team_id": team_id,
            "nodes": nodes,
            "active": active,
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestBlueprintCRUD:
    def test_create_blueprint(self, client: TestClient) -> None:
        data = _create_blueprint(client)
        assert data["name"] == "my-blueprint"
        assert data["team_id"] == "team-1"
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["name"] == "lint"
        assert data["nodes"][0]["node_type"] == "deterministic"
        assert data["active"] is True

    def test_list_blueprints(self, client: TestClient) -> None:
        _create_blueprint(client, name="bp-a")
        _create_blueprint(client, name="bp-b")
        resp = client.get("/api/v1/workflow-blueprints")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_blueprint(self, client: TestClient) -> None:
        created = _create_blueprint(client)
        bp_id = created["blueprint_id"]
        resp = client.get(f"/api/v1/workflow-blueprints/{bp_id}")
        assert resp.status_code == 200
        assert resp.json()["blueprint_id"] == bp_id

    def test_get_blueprint_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflow-blueprints/nonexistent")
        assert resp.status_code == 404

    def test_update_blueprint(self, client: TestClient) -> None:
        created = _create_blueprint(client)
        bp_id = created["blueprint_id"]
        resp = client.patch(
            f"/api/v1/workflow-blueprints/{bp_id}",
            json={"name": "updated-name", "description": "new desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated-name"
        assert resp.json()["description"] == "new desc"

    def test_update_blueprint_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/workflow-blueprints/nonexistent",
            json={"name": "x"},
        )
        assert resp.status_code == 404

    def test_delete_blueprint(self, client: TestClient) -> None:
        created = _create_blueprint(client)
        bp_id = created["blueprint_id"]
        resp = client.delete(f"/api/v1/workflow-blueprints/{bp_id}")
        assert resp.status_code == 204
        resp = client.get(f"/api/v1/workflow-blueprints/{bp_id}")
        assert resp.status_code == 404

    def test_delete_blueprint_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/workflow-blueprints/nonexistent")
        assert resp.status_code == 404


class TestBlueprintActivation:
    def test_activate_blueprint(self, client: TestClient) -> None:
        created = _create_blueprint(client, active=False)
        bp_id = created["blueprint_id"]
        resp = client.post(f"/api/v1/workflow-blueprints/{bp_id}/activate")
        assert resp.status_code == 200
        assert resp.json()["active"] is True

    def test_deactivate_blueprint(self, client: TestClient) -> None:
        created = _create_blueprint(client, active=True)
        bp_id = created["blueprint_id"]
        resp = client.post(f"/api/v1/workflow-blueprints/{bp_id}/deactivate")
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_activate_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/workflow-blueprints/nonexistent/activate")
        assert resp.status_code == 404

    def test_deactivate_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/workflow-blueprints/nonexistent/deactivate")
        assert resp.status_code == 404


class TestBlueprintNodes:
    def test_list_nodes(self, client: TestClient) -> None:
        created = _create_blueprint(client)
        bp_id = created["blueprint_id"]
        resp = client.get(f"/api/v1/workflow-blueprints/{bp_id}/nodes")
        assert resp.status_code == 200
        nodes = resp.json()
        assert len(nodes) == 2
        assert nodes[0]["name"] == "lint"

    def test_list_nodes_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflow-blueprints/nonexistent/nodes")
        assert resp.status_code == 404


class TestNodeTypes:
    def test_list_node_types(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflow-blueprints/node-types")
        assert resp.status_code == 200
        types = resp.json()
        assert len(types) == 5
        values = {t["value"] for t in types}
        assert "deterministic" in values
        assert "agentic" in values
        assert "human_review" in values
        assert "conditional" in values
        assert "parallel" in values
