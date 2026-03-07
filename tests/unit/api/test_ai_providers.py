"""Tests for the AI provider management API endpoints."""

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


class TestAIProvidersAPI:
    def test_create_provider(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "anthropic-1",
                "provider_type": "anthropic",
                "name": "Anthropic Production",
                "api_key": "sk-ant-api03-xxxxxxxxxxxxxxxxxxxx",
                "is_default": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider_id"] == "anthropic-1"
        assert data["provider_type"] == "anthropic"
        assert data["is_default"] is True
        assert data["has_api_key"] is True
        assert "api_key_preview" in data
        assert "xxxxxxxxxxxxxxxxxxxx" not in data.get("api_key_preview", "")

    def test_create_provider_without_key(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "ollama-local",
                "provider_type": "ollama",
                "name": "Local Ollama",
                "api_base": "http://localhost:11434",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["has_api_key"] is False

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "provider_id": "p1",
            "provider_type": "anthropic",
            "name": "P1",
            "api_key": "sk-ant-test-key-12345678",
        }
        client.post("/api/v1/ai-providers", json=body)
        resp = client.post("/api/v1/ai-providers", json=body)
        assert resp.status_code == 409

    def test_list_providers_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai-providers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_providers(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "anthropic",
                "name": "A",
                "api_key": "sk-ant-test-12345678",
            },
        )
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p2",
                "provider_type": "openai",
                "name": "B",
                "api_key": "sk-test-12345678",
            },
        )
        resp = client.get("/api/v1/ai-providers")
        assert len(resp.json()) == 2

    def test_list_provider_types(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai-providers/types")
        assert resp.status_code == 200
        types = resp.json()
        type_names = [t["provider_type"] for t in types]
        assert "anthropic" in type_names
        assert "openai" in type_names
        assert "ollama" in type_names
        assert "azure_openai" in type_names
        # Ollama should hide api_key
        ollama = next(t for t in types if t["provider_type"] == "ollama")
        assert "api_key" in ollama["hidden_fields"]
        assert "api_base" in ollama["required_fields"]

    def test_get_provider(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "anthropic",
                "name": "A",
                "api_key": "sk-ant-test-12345678",
            },
        )
        resp = client.get("/api/v1/ai-providers/p1")
        assert resp.status_code == 200
        assert resp.json()["provider_id"] == "p1"

    def test_get_provider_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai-providers/nope")
        assert resp.status_code == 404

    def test_get_default_provider(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "anthropic",
                "name": "Default",
                "api_key": "sk-ant-test-12345678",
                "is_default": True,
            },
        )
        resp = client.get("/api/v1/ai-providers/default")
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True

    def test_get_default_provider_none_set(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai-providers/default")
        assert resp.status_code == 404

    def test_update_provider(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "anthropic",
                "name": "Old",
                "api_key": "sk-ant-test-12345678",
            },
        )
        resp = client.patch(
            "/api/v1/ai-providers/p1",
            json={"name": "New Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"

    def test_update_provider_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/ai-providers/nope", json={"name": "x"})
        assert resp.status_code == 404

    def test_update_api_key(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "openai",
                "name": "OAI",
                "api_key": "sk-test-12345678",
            },
        )
        resp = client.put(
            "/api/v1/ai-providers/p1/api-key",
            json={"api_key": "sk-new-secret-key-12345"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"
        assert "api_key_preview" in resp.json()
        # Verify has_api_key is now true
        detail = client.get("/api/v1/ai-providers/p1").json()
        assert detail["has_api_key"] is True

    def test_update_api_key_not_found(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/ai-providers/nope/api-key",
            json={"api_key": "sk-xxx"},
        )
        assert resp.status_code == 404

    def test_delete_provider(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "anthropic",
                "name": "A",
                "api_key": "sk-ant-test-12345678",
            },
        )
        resp = client.delete("/api/v1/ai-providers/p1")
        assert resp.status_code == 204
        assert client.get("/api/v1/ai-providers/p1").status_code == 404

    def test_delete_provider_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/ai-providers/nope")
        assert resp.status_code == 404

    def test_create_anthropic_requires_api_key(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai-providers",
            json={"provider_id": "p1", "provider_type": "anthropic", "name": "A"},
        )
        assert resp.status_code == 422
        assert "api_key is required" in resp.json()["detail"]

    def test_create_ollama_rejects_api_key(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "ollama",
                "name": "Ollama",
                "api_base": "http://localhost:11434",
                "api_key": "should-not-be-here",
            },
        )
        assert resp.status_code == 422
        assert "not used" in resp.json()["detail"]

    def test_create_ollama_requires_api_base(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai-providers",
            json={"provider_id": "p1", "provider_type": "ollama", "name": "Ollama"},
        )
        assert resp.status_code == 422
        assert "api_base is required" in resp.json()["detail"]

    def test_list_provider_models(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "anthropic",
                "name": "Anthropic",
                "api_key": "sk-ant-test-12345678",
            },
        )
        client.post(
            "/api/v1/models",
            json={
                "model_id": "m1",
                "provider_id": "p1",
                "name": "Claude Sonnet",
                "model_name": "claude-sonnet-4-20250514",
            },
        )
        resp = client.get("/api/v1/ai-providers/p1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["model_id"] == "m1"
        assert data[0]["provider_name"] == "Anthropic"

    def test_list_provider_models_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai-providers/nonexistent/models")
        assert resp.status_code == 404

    def test_api_key_not_exposed_in_list(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "anthropic",
                "name": "A",
                "api_key": "sk-ant-supersecret",
            },
        )
        resp = client.get("/api/v1/ai-providers")
        for p in resp.json():
            assert "api_key" not in p
            assert "sk-ant-supersecret" not in str(p)
