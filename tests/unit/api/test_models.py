"""Tests for the AI model and model assignment management API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def _create_provider(client: TestClient, provider_id: str = "prov-1") -> dict:
    resp = client.post(
        "/api/v1/ai-providers",
        json={
            "provider_id": provider_id,
            "provider_type": "anthropic",
            "name": "Anthropic",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_model(
    client: TestClient,
    model_id: str = "model-1",
    provider_id: str = "prov-1",
) -> dict:
    resp = client.post(
        "/api/v1/models",
        json={
            "model_id": model_id,
            "provider_id": provider_id,
            "name": "Claude Sonnet 4",
            "model_name": "claude-sonnet-4-20250514",
            "capabilities": ["coding", "planning"],
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestModelsAPI:
    def test_create_model(self, client: TestClient) -> None:
        _create_provider(client)
        data = _create_model(client)
        assert data["model_id"] == "model-1"
        assert data["provider_id"] == "prov-1"
        assert data["name"] == "Claude Sonnet 4"
        assert data["model_name"] == "claude-sonnet-4-20250514"
        assert data["provider_name"] == "Anthropic"
        assert data["provider_type"] == "anthropic"
        assert data["capabilities"] == ["coding", "planning"]

    def test_create_model_missing_provider(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/models",
            json={
                "provider_id": "nonexistent",
                "name": "Test",
                "model_name": "test",
            },
        )
        assert resp.status_code == 404

    def test_create_duplicate_model(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        resp = client.post(
            "/api/v1/models",
            json={
                "model_id": "model-1",
                "provider_id": "prov-1",
                "name": "Dup",
                "model_name": "dup",
            },
        )
        assert resp.status_code == 409

    def test_list_models(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client, model_id="m1")
        _create_model(client, model_id="m2")
        resp = client.get("/api/v1/models")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_models_by_provider(self, client: TestClient) -> None:
        _create_provider(client, provider_id="prov-1")
        _create_provider(client, provider_id="prov-2")
        _create_model(client, model_id="m1", provider_id="prov-1")
        _create_model(client, model_id="m2", provider_id="prov-2")
        resp = client.get("/api/v1/models", params={"provider_id": "prov-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["model_id"] == "m1"

    def test_get_model(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        resp = client.get("/api/v1/models/model-1")
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "model-1"

    def test_get_model_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/models/nonexistent")
        assert resp.status_code == 404

    def test_update_model(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        resp = client.patch(
            "/api/v1/models/model-1",
            json={"name": "Updated Name", "max_tokens": 8192},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["max_tokens"] == 8192
        assert data["model_name"] == "claude-sonnet-4-20250514"

    def test_delete_model(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        resp = client.delete("/api/v1/models/model-1")
        assert resp.status_code == 204
        resp = client.get("/api/v1/models/model-1")
        assert resp.status_code == 404

    def test_delete_model_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/models/nonexistent")
        assert resp.status_code == 404


class TestModelAssignmentsAPI:
    def test_create_assignment(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        resp = client.post(
            "/api/v1/models/model-1/assignments",
            json={
                "assignment_id": "a1",
                "context": "agent_role",
                "context_id": "coder",
                "priority": 10,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["assignment_id"] == "a1"
        assert data["model_id"] == "model-1"
        assert data["context"] == "agent_role"
        assert data["priority"] == 10

    def test_create_assignment_model_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/models/nonexistent/assignments",
            json={
                "context": "task",
                "context_id": "default",
            },
        )
        assert resp.status_code == 404

    def test_list_assignments_by_model(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        client.post(
            "/api/v1/models/model-1/assignments",
            json={"assignment_id": "a1", "context": "agent_role", "context_id": "coder"},
        )
        client.post(
            "/api/v1/models/model-1/assignments",
            json={"assignment_id": "a2", "context": "chat", "context_id": "default"},
        )
        resp = client.get("/api/v1/models/model-1/assignments")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_all_assignments_filtered_by_context(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        client.post(
            "/api/v1/models/model-1/assignments",
            json={"assignment_id": "a1", "context": "agent_role", "context_id": "coder"},
        )
        client.post(
            "/api/v1/models/model-1/assignments",
            json={"assignment_id": "a2", "context": "chat", "context_id": "default"},
        )
        resp = client.get("/api/v1/model-assignments", params={"context": "agent_role"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["context"] == "agent_role"

    def test_delete_assignment(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        client.post(
            "/api/v1/models/model-1/assignments",
            json={"assignment_id": "a1", "context": "task", "context_id": "default"},
        )
        resp = client.delete("/api/v1/model-assignments/a1")
        assert resp.status_code == 204
        resp = client.get("/api/v1/model-assignments")
        assert len(resp.json()) == 0

    def test_delete_assignment_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/model-assignments/nonexistent")
        assert resp.status_code == 404

    def test_delete_model_cascades_assignments(self, client: TestClient) -> None:
        _create_provider(client)
        _create_model(client)
        client.post(
            "/api/v1/models/model-1/assignments",
            json={"assignment_id": "a1", "context": "task", "context_id": "default"},
        )
        client.post(
            "/api/v1/models/model-1/assignments",
            json={"assignment_id": "a2", "context": "chat", "context_id": "default"},
        )
        resp = client.delete("/api/v1/models/model-1")
        assert resp.status_code == 204
        resp = client.get("/api/v1/model-assignments")
        assert len(resp.json()) == 0
