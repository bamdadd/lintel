"""In-memory cloud environment store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.cloud_environments_api.types import CloudEnvironment


class InMemoryCloudEnvironmentStore:
    """Simple in-memory store for cloud environments."""

    def __init__(self) -> None:
        self._envs: dict[str, CloudEnvironment] = {}

    async def add(self, env: CloudEnvironment) -> None:
        self._envs[env.cloud_environment_id] = env

    async def get(self, cloud_environment_id: str) -> CloudEnvironment | None:
        return self._envs.get(cloud_environment_id)

    async def list_all(self) -> list[CloudEnvironment]:
        return list(self._envs.values())

    async def update(self, env: CloudEnvironment) -> None:
        self._envs[env.cloud_environment_id] = env

    async def remove(self, cloud_environment_id: str) -> None:
        del self._envs[cloud_environment_id]
