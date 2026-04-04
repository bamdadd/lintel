"""In-memory stores for environment prebuilds."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.env_prebuilds_api.types import PrebuildConfig, PrebuildRun


class InMemoryPrebuildConfigStore:
    """Simple in-memory store for prebuild configs."""

    def __init__(self) -> None:
        self._configs: dict[str, PrebuildConfig] = {}

    async def add(self, config: PrebuildConfig) -> None:
        self._configs[config.config_id] = config

    async def get(self, config_id: str) -> PrebuildConfig | None:
        return self._configs.get(config_id)

    async def list_all(self) -> list[PrebuildConfig]:
        return list(self._configs.values())

    async def remove(self, config_id: str) -> None:
        del self._configs[config_id]


class InMemoryPrebuildRunStore:
    """Simple in-memory store for prebuild runs."""

    def __init__(self) -> None:
        self._runs: dict[str, PrebuildRun] = {}

    async def add(self, run: PrebuildRun) -> None:
        self._runs[run.run_id] = run

    async def get(self, run_id: str) -> PrebuildRun | None:
        return self._runs.get(run_id)

    async def list_all(self) -> list[PrebuildRun]:
        return list(self._runs.values())

    async def list_by_config(self, config_id: str) -> list[PrebuildRun]:
        return [r for r in self._runs.values() if r.config_id == config_id]
