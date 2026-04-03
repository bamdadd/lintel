"""Tests for DatabaseReplica type and SandboxConfig.replica_connections."""

from lintel.sandbox.types import DatabaseReplica, SandboxConfig


class TestDatabaseReplica:
    def test_defaults(self) -> None:
        replica = DatabaseReplica(name="staging", host="staging.db")
        assert replica.port == 5432
        assert replica.database == "postgres"
        assert replica.read_only is True
        assert replica.credential_ref == ""

    def test_custom_values(self) -> None:
        replica = DatabaseReplica(
            name="analytics",
            host="analytics.db",
            port=5433,
            database="analytics",
            read_only=False,
            credential_ref="cred-123",
        )
        assert replica.name == "analytics"
        assert replica.host == "analytics.db"
        assert replica.port == 5433
        assert replica.database == "analytics"
        assert replica.read_only is False
        assert replica.credential_ref == "cred-123"

    def test_frozen(self) -> None:
        replica = DatabaseReplica(name="staging", host="staging.db")
        try:
            replica.host = "other.db"  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass


class TestSandboxConfigReplicaConnections:
    def test_default_empty(self) -> None:
        config = SandboxConfig()
        assert config.replica_connections == ()

    def test_with_replicas(self) -> None:
        replicas = (
            DatabaseReplica(name="staging", host="staging.db"),
            DatabaseReplica(name="analytics", host="analytics.db", port=5433),
        )
        config = SandboxConfig(replica_connections=replicas)
        assert len(config.replica_connections) == 2
        assert config.replica_connections[0].name == "staging"
        assert config.replica_connections[1].port == 5433
