"""Tests for database replica env var injection during sandbox creation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from fastapi.testclient import TestClient

from lintel.api.app import create_app
from lintel.sandboxes_api.replica_store import (
    DatabaseReplicaConfig,
    InMemoryReplicaConfigStore,
)
from lintel.sandboxes_api.routes import SandboxStore


@pytest.fixture()
def client(dummy_sandbox_manager: object) -> Generator[TestClient]:
    app = create_app()
    with TestClient(app) as c:
        app.state.sandbox_manager = dummy_sandbox_manager
        app.state.sandbox_store = SandboxStore()
        app.state.replica_config_store = InMemoryReplicaConfigStore()
        yield c


class TestInlineReplicaInjection:
    def test_inline_replicas_produce_env_vars(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "replica_connections": [
                    {
                        "name": "staging",
                        "host": "staging.db.internal",
                        "port": 5432,
                        "database": "mydb",
                        "read_only": True,
                        "credential_ref": "cred-1",
                    },
                ],
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        env = dict(config.environment)
        assert env["DB_REPLICA_STAGING_HOST"] == "staging.db.internal"
        assert env["DB_REPLICA_STAGING_PORT"] == "5432"
        assert env["DB_REPLICA_STAGING_DATABASE"] == "mydb"
        assert env["DB_REPLICA_STAGING_READ_ONLY"] == "true"
        assert env["DB_REPLICA_STAGING_CREDENTIAL_REF"] == "cred-1"
        assert env["DB_REPLICA_NAMES"] == "staging"

    def test_multiple_replicas(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "replica_connections": [
                    {"name": "primary", "host": "primary.db"},
                    {"name": "analytics", "host": "analytics.db", "port": 5433},
                ],
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        env = dict(config.environment)
        assert env["DB_REPLICA_PRIMARY_HOST"] == "primary.db"
        assert env["DB_REPLICA_ANALYTICS_HOST"] == "analytics.db"
        assert env["DB_REPLICA_ANALYTICS_PORT"] == "5433"
        assert env["DB_REPLICA_NAMES"] == "primary,analytics"

    def test_no_replicas_no_env_vars(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        assert len(config.environment) == 0

    def test_replica_domain_objects_on_config(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "replica_connections": [
                    {"name": "staging", "host": "staging.db", "database": "app"},
                ],
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        assert len(config.replica_connections) == 1
        assert config.replica_connections[0].name == "staging"
        assert config.replica_connections[0].host == "staging.db"
        assert config.replica_connections[0].database == "app"
        assert config.replica_connections[0].read_only is True


def _seed_project_replicas(client: TestClient) -> None:
    """Synchronously seed a project replica into the store."""
    store = client.app.state.replica_config_store  # type: ignore[union-attr]
    store._replicas["pr1"] = DatabaseReplicaConfig(
        replica_id="pr1",
        project_id="proj1",
        name="prod-replica",
        host="prod.db.internal",
        port=5432,
        database="proddb",
        read_only=True,
        credential_ref="cred-prod",
    )


class TestProjectReplicaInjection:
    def test_project_replicas_injected(self, client: TestClient) -> None:
        _seed_project_replicas(client)

        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "project_id": "proj1",
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        env = dict(config.environment)
        assert env["DB_REPLICA_PROD_REPLICA_HOST"] == "prod.db.internal"
        assert env["DB_REPLICA_PROD_REPLICA_DATABASE"] == "proddb"
        assert env["DB_REPLICA_NAMES"] == "prod-replica"

    def test_inline_and_project_replicas_merged(self, client: TestClient) -> None:
        _seed_project_replicas(client)

        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "project_id": "proj1",
                "replica_connections": [
                    {"name": "staging", "host": "staging.db"},
                ],
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        env = dict(config.environment)
        assert env["DB_REPLICA_STAGING_HOST"] == "staging.db"
        assert env["DB_REPLICA_PROD_REPLICA_HOST"] == "prod.db.internal"
        assert env["DB_REPLICA_NAMES"] == "staging,prod-replica"
        assert len(config.replica_connections) == 2

    def test_credential_ref_omitted_when_empty(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "replica_connections": [
                    {"name": "staging", "host": "staging.db"},
                ],
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        env = dict(config.environment)
        assert "DB_REPLICA_STAGING_CREDENTIAL_REF" not in env
