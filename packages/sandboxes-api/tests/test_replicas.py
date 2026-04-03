"""Tests for database replica config CRUD endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.sandboxes_api.replica_store import InMemoryReplicaConfigStore
from lintel.sandboxes_api.replicas import replica_config_store_provider, router

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryReplicaConfigStore()
    replica_config_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    replica_config_store_provider.override(None)


def _create_replica(
    client: TestClient,
    project_id: str = "proj1",
    replica_id: str = "r1",
    name: str = "staging-db",
    host: str = "staging.db.internal",
) -> dict:  # type: ignore[type-arg]
    return client.post(
        f"/api/v1/projects/{project_id}/replica-configs",
        json={
            "replica_id": replica_id,
            "project_id": project_id,
            "name": name,
            "host": host,
            "port": 5432,
            "database": "mydb",
            "read_only": True,
            "credential_ref": "cred-abc",
        },
    ).json()


class TestCreateReplicaConfig:
    def test_create(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/proj1/replica-configs",
            json={
                "replica_id": "r1",
                "project_id": "proj1",
                "name": "staging-db",
                "host": "staging.db.internal",
                "port": 5432,
                "database": "mydb",
                "read_only": True,
                "credential_ref": "cred-abc",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["replica_id"] == "r1"
        assert data["project_id"] == "proj1"
        assert data["name"] == "staging-db"
        assert data["host"] == "staging.db.internal"
        assert data["port"] == 5432
        assert data["database"] == "mydb"
        assert data["read_only"] is True
        assert data["credential_ref"] == "cred-abc"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        _create_replica(client, replica_id="dup")
        resp = client.post(
            "/api/v1/projects/proj1/replica-configs",
            json={
                "replica_id": "dup",
                "project_id": "proj1",
                "name": "other",
                "host": "other.db",
            },
        )
        assert resp.status_code == 409

    def test_create_overrides_project_id_from_path(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/proj-path/replica-configs",
            json={
                "project_id": "proj-body",
                "name": "staging-db",
                "host": "staging.db.internal",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["project_id"] == "proj-path"

    def test_create_defaults(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/proj1/replica-configs",
            json={
                "name": "staging-db",
                "host": "staging.db.internal",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["port"] == 5432
        assert data["database"] == "postgres"
        assert data["read_only"] is True
        assert data["credential_ref"] == ""


class TestListReplicaConfigs:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/proj1/replica-configs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_filters_by_project(self, client: TestClient) -> None:
        _create_replica(client, project_id="proj1", replica_id="r1")
        _create_replica(client, project_id="proj2", replica_id="r2")
        resp = client.get("/api/v1/projects/proj1/replica-configs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "proj1"


class TestGetReplicaConfig:
    def test_get(self, client: TestClient) -> None:
        _create_replica(client, replica_id="r1")
        resp = client.get("/api/v1/projects/proj1/replica-configs/r1")
        assert resp.status_code == 200
        assert resp.json()["replica_id"] == "r1"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/proj1/replica-configs/missing")
        assert resp.status_code == 404

    def test_wrong_project_returns_404(self, client: TestClient) -> None:
        _create_replica(client, project_id="proj1", replica_id="r1")
        resp = client.get("/api/v1/projects/other-proj/replica-configs/r1")
        assert resp.status_code == 404


class TestUpdateReplicaConfig:
    def test_update(self, client: TestClient) -> None:
        _create_replica(client, replica_id="r1")
        resp = client.patch(
            "/api/v1/projects/proj1/replica-configs/r1",
            json={"name": "prod-db", "port": 5433},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "prod-db"
        assert resp.json()["port"] == 5433

    def test_update_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/projects/proj1/replica-configs/missing",
            json={"name": "x"},
        )
        assert resp.status_code == 404


class TestDeleteReplicaConfig:
    def test_delete(self, client: TestClient) -> None:
        _create_replica(client, replica_id="r1")
        resp = client.delete("/api/v1/projects/proj1/replica-configs/r1")
        assert resp.status_code == 204
        assert client.get("/api/v1/projects/proj1/replica-configs/r1").status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/projects/proj1/replica-configs/missing")
        assert resp.status_code == 404
