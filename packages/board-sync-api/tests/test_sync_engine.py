"""Tests for the sync engine."""

from __future__ import annotations

from lintel.board_sync_api.store import BoardSyncConfigStore, ExternalIdMappingStore
from lintel.board_sync_api.sync_engine import SyncEngine
from lintel.board_sync_api.types import SyncDirection, SyncStatus


async def test_sync_marks_connected() -> None:
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    config = {
        "sync_config_id": "sc1",
        "board_id": "b1",
        "provider": "jira",
        "direction": SyncDirection.BIDIRECTIONAL,
        "status": SyncStatus.DISCONNECTED,
    }
    await config_store.add(config)
    engine = SyncEngine(config_store, mapping_store)
    result = await engine.sync("sc1", work_items=[])
    assert result["status"] == SyncStatus.CONNECTED

    updated = await config_store.get("sc1")
    assert updated is not None
    assert updated["last_synced"] != ""


async def test_sync_push_updates_mapping() -> None:
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    config = {
        "sync_config_id": "sc1",
        "board_id": "b1",
        "provider": "jira",
        "direction": SyncDirection.PUSH,
        "status": SyncStatus.CONNECTED,
    }
    await config_store.add(config)
    mapping = {
        "mapping_id": "m1",
        "sync_config_id": "sc1",
        "work_item_id": "wi-1",
        "external_id": "PROJ-1",
        "last_synced": "",
    }
    await mapping_store.add(mapping)

    engine = SyncEngine(config_store, mapping_store)
    result = await engine.sync(
        "sc1",
        work_items=[{"work_item_id": "wi-1", "status": "in_progress", "title": "Test"}],
    )
    assert result["pushed"] == 1

    updated_mapping = await mapping_store.get("m1")
    assert updated_mapping is not None
    assert updated_mapping["last_synced"] != ""


async def test_sync_config_not_found() -> None:
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    engine = SyncEngine(config_store, mapping_store)
    try:
        await engine.sync("missing", work_items=[])
        msg = "Expected ValueError"
        raise AssertionError(msg)
    except ValueError:
        pass
