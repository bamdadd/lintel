"""In-memory environment store."""

from lintel.domain.types import Environment


class InMemoryEnvironmentStore:
    """Simple in-memory store for environments."""

    def __init__(self) -> None:
        self._envs: dict[str, Environment] = {}

    async def add(self, env: Environment) -> None:
        self._envs[env.environment_id] = env

    async def get(self, environment_id: str) -> Environment | None:
        return self._envs.get(environment_id)

    async def list_all(self) -> list[Environment]:
        return list(self._envs.values())

    async def update(self, env: Environment) -> None:
        self._envs[env.environment_id] = env

    async def remove(self, environment_id: str) -> None:
        del self._envs[environment_id]
