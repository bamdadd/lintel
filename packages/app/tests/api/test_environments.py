"""Tests for environments API."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from lintel.api.app import create_app
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_environment(
    client: TestClient,
    environment_id: str = "env1",
) -> dict:
    return client.post(
        "/api/v1/environments",
        json={
            "environment_id": environment_id,
            "name": "Dev Env",
        },
    ).json()


class TestEnvironmentsAPI:
    def test_create_environment(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/environments",
            json={
                "environment_id": "env1",
                "name": "Production",
                "env_type": "production",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["environment_id"] == "env1"
        assert data["name"] == "Production"
        assert data["env_type"] == "production"

    def test_create_environment_duplicate_returns_409(
        self,
        client: TestClient,
    ) -> None:
        _create_environment(client, "dup")
        resp = client.post(
            "/api/v1/environments",
            json={"environment_id": "dup", "name": "Again"},
        )
        assert resp.status_code == 409

    def test_list_environments_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/environments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_environments_with_items(
        self,
        client: TestClient,
    ) -> None:
        _create_environment(client, "a")
        _create_environment(client, "b")
        resp = client.get("/api/v1/environments")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_environment_by_id(self, client: TestClient) -> None:
        _create_environment(client, "env1")
        resp = client.get("/api/v1/environments/env1")
        assert resp.status_code == 200
        assert resp.json()["environment_id"] == "env1"

    def test_get_environment_not_found_returns_404(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/environments/missing")
        assert resp.status_code == 404

    def test_update_environment(self, client: TestClient) -> None:
        _create_environment(client, "env1")
        resp = client.patch(
            "/api/v1/environments/env1",
            json={"name": "Staging", "env_type": "staging"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Staging"
        assert resp.json()["env_type"] == "staging"

    def test_delete_environment(self, client: TestClient) -> None:
        _create_environment(client, "env1")
        resp = client.delete("/api/v1/environments/env1")
        assert resp.status_code == 204
        assert client.get("/api/v1/environments/env1").status_code == 404
