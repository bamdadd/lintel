"""In-memory store for database replica configurations per project."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class DatabaseReplicaConfig:
    """Persisted configuration for a database replica attached to a project."""

    replica_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    name: str = ""
    host: str = ""
    port: int = 5432
    database: str = "postgres"
    read_only: bool = True
    credential_ref: str = ""


class InMemoryReplicaConfigStore:
    """Simple in-memory CRUD store for replica configurations."""

    def __init__(self) -> None:
        self._replicas: dict[str, DatabaseReplicaConfig] = {}

    async def add(self, replica: DatabaseReplicaConfig) -> None:
        self._replicas[replica.replica_id] = replica

    async def get(self, replica_id: str) -> DatabaseReplicaConfig | None:
        return self._replicas.get(replica_id)

    async def list_for_project(self, project_id: str) -> list[DatabaseReplicaConfig]:
        return [r for r in self._replicas.values() if r.project_id == project_id]

    async def list_all(self) -> list[DatabaseReplicaConfig]:
        return list(self._replicas.values())

    async def update(self, replica: DatabaseReplicaConfig) -> None:
        self._replicas[replica.replica_id] = replica

    async def remove(self, replica_id: str) -> None:
        self._replicas.pop(replica_id, None)
