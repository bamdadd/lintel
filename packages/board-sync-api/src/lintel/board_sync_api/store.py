"""In-memory stores for board sync state."""

from __future__ import annotations

from typing import Any


class BoardSyncConfigStore:
    """Stores sync integration configs (provider, direction, credentials, etc.)."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, config: dict[str, Any]) -> None:
        self._data[config["sync_config_id"]] = config

    async def get(self, sync_config_id: str) -> dict[str, Any] | None:
        return self._data.get(sync_config_id)

    async def list_by_board(self, board_id: str) -> list[dict[str, Any]]:
        return [c for c in self._data.values() if c.get("board_id") == board_id]

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def update(self, sync_config_id: str, data: dict[str, Any]) -> None:
        self._data[sync_config_id] = data

    async def remove(self, sync_config_id: str) -> None:
        self._data.pop(sync_config_id, None)


class ExternalIdMappingStore:
    """Maps work_item_id ↔ external_id (Jira issue key / Notion page ID)."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, mapping: dict[str, Any]) -> None:
        self._data[mapping["mapping_id"]] = mapping

    async def get(self, mapping_id: str) -> dict[str, Any] | None:
        return self._data.get(mapping_id)

    async def get_by_work_item(
        self,
        sync_config_id: str,
        work_item_id: str,
    ) -> dict[str, Any] | None:
        for m in self._data.values():
            if m.get("sync_config_id") == sync_config_id and m.get("work_item_id") == work_item_id:
                return m
        return None

    async def get_by_external_id(
        self,
        sync_config_id: str,
        external_id: str,
    ) -> dict[str, Any] | None:
        for m in self._data.values():
            if m.get("sync_config_id") == sync_config_id and m.get("external_id") == external_id:
                return m
        return None

    async def list_by_config(self, sync_config_id: str) -> list[dict[str, Any]]:
        return [m for m in self._data.values() if m.get("sync_config_id") == sync_config_id]

    async def update(self, mapping_id: str, data: dict[str, Any]) -> None:
        self._data[mapping_id] = data

    async def remove(self, mapping_id: str) -> None:
        self._data.pop(mapping_id, None)
