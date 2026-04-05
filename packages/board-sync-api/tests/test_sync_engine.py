"""Tests for the sync engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from lintel.board_sync_api.store import BoardSyncConfigStore, ExternalIdMappingStore
from lintel.board_sync_api.sync_engine import SyncEngine, _resolve_conflict
from lintel.board_sync_api.types import ConflictStrategy, SyncDirection, SyncStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    sync_config_id: str = "sc1",
    *,
    direction: str = SyncDirection.BIDIRECTIONAL,
    provider: str = "jira",
    conflict_strategy: str = ConflictStrategy.LAST_WRITE_WINS,
) -> dict[str, object]:
    return {
        "sync_config_id": sync_config_id,
        "board_id": "b1",
        "provider": provider,
        "direction": direction,
        "conflict_strategy": conflict_strategy,
        "status": SyncStatus.DISCONNECTED,
        "last_synced": "",
    }


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------


class TestConflictResolution:
    def test_last_write_wins_remote_newer(self) -> None:
        assert (
            _resolve_conflict(
                {"updated_at": "2025-01-01T00:00:00"},
                {"updated_at": "2025-06-01T00:00:00"},
                ConflictStrategy.LAST_WRITE_WINS,
            )
            == "remote"
        )

    def test_last_write_wins_local_newer(self) -> None:
        assert (
            _resolve_conflict(
                {"updated_at": "2025-06-01T00:00:00"},
                {"updated_at": "2025-01-01T00:00:00"},
                ConflictStrategy.LAST_WRITE_WINS,
            )
            == "local"
        )

    def test_manual_always_keeps_local(self) -> None:
        assert (
            _resolve_conflict(
                {"updated_at": "2020-01-01"},
                {"updated_at": "2030-01-01"},
                ConflictStrategy.MANUAL,
            )
            == "local"
        )


# ---------------------------------------------------------------------------
# Sync — basic lifecycle
# ---------------------------------------------------------------------------


async def test_sync_marks_connected() -> None:
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    await config_store.add(_make_config())

    engine = SyncEngine(config_store, mapping_store)
    result = await engine.sync("sc1", work_items=[])
    assert result["status"] == SyncStatus.CONNECTED

    updated = await config_store.get("sc1")
    assert updated is not None
    assert updated["last_synced"] != ""


async def test_sync_config_not_found() -> None:
    engine = SyncEngine(BoardSyncConfigStore(), ExternalIdMappingStore())
    try:
        await engine.sync("missing", work_items=[])
        msg = "Expected ValueError"
        raise AssertionError(msg)
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------


async def test_sync_push_updates_existing_mapping() -> None:
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    await config_store.add(_make_config(direction=SyncDirection.PUSH))
    await mapping_store.add(
        {
            "mapping_id": "m1",
            "sync_config_id": "sc1",
            "work_item_id": "wi-1",
            "external_id": "PROJ-1",
            "last_synced": "",
        }
    )

    engine = SyncEngine(config_store, mapping_store)
    result = await engine.sync(
        "sc1",
        work_items=[{"work_item_id": "wi-1", "status": "in_progress", "title": "Test"}],
    )
    assert result["pushed"] == 1

    m = await mapping_store.get("m1")
    assert m is not None
    assert m["last_synced"] != ""


async def test_sync_push_creates_new_mapping() -> None:
    """Push an item that has no mapping yet — should create external item + mapping."""
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    await config_store.add(_make_config(direction=SyncDirection.PUSH))

    engine = SyncEngine(config_store, mapping_store)
    result = await engine.sync(
        "sc1",
        work_items=[{"work_item_id": "wi-new", "status": "open", "title": "Brand new"}],
    )
    assert result["pushed"] == 1

    mappings = await mapping_store.list_by_config("sc1")
    assert len(mappings) == 1
    assert mappings[0]["work_item_id"] == "wi-new"


# ---------------------------------------------------------------------------
# Pull
# ---------------------------------------------------------------------------


async def test_sync_pull_creates_mappings() -> None:
    """Pull items from external system and verify mappings are created."""
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    await config_store.add(_make_config(direction=SyncDirection.PULL))

    mock_adapter = AsyncMock()
    mock_adapter.pull_items = AsyncMock(
        return_value=[
            {"external_id": "ext-1", "title": "Task A", "status": "open"},
            {"external_id": "ext-2", "title": "Task B", "status": "done"},
        ]
    )
    mock_adapter.map_status_outbound = lambda s: s

    with patch("lintel.board_sync_api.sync_engine.get_adapter", return_value=mock_adapter):
        engine = SyncEngine(config_store, mapping_store)
        result = await engine.sync("sc1", work_items=[])

    assert result["pulled"] == 2
    assert len(result["pulled_items"]) == 2
    assert result["pulled_items"][0]["title"] == "Task A"

    mappings = await mapping_store.list_by_config("sc1")
    assert len(mappings) == 2


async def test_sync_pull_existing_item_updates_mapping() -> None:
    """Pull-only: when item already mapped, still accept and update mapping."""
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    await config_store.add(_make_config(direction=SyncDirection.PULL))
    await mapping_store.add(
        {
            "mapping_id": "m1",
            "sync_config_id": "sc1",
            "work_item_id": "wi-1",
            "external_id": "ext-1",
            "last_synced": "",
        }
    )

    mock_adapter = AsyncMock()
    mock_adapter.pull_items = AsyncMock(
        return_value=[
            {"external_id": "ext-1", "title": "Updated Task", "status": "done"},
        ]
    )

    with patch("lintel.board_sync_api.sync_engine.get_adapter", return_value=mock_adapter):
        engine = SyncEngine(config_store, mapping_store)
        result = await engine.sync("sc1", work_items=[])

    assert result["pulled"] == 1
    m = await mapping_store.get("m1")
    assert m is not None
    assert m["last_synced"] != ""


# ---------------------------------------------------------------------------
# Bidirectional with conflict
# ---------------------------------------------------------------------------


async def test_sync_bidirectional_remote_wins_on_newer_timestamp() -> None:
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    await config_store.add(_make_config(direction=SyncDirection.BIDIRECTIONAL))
    await mapping_store.add(
        {
            "mapping_id": "m1",
            "sync_config_id": "sc1",
            "work_item_id": "wi-1",
            "external_id": "ext-1",
            "last_synced": "",
        }
    )

    mock_adapter = AsyncMock()
    mock_adapter.pull_items = AsyncMock(
        return_value=[
            {
                "external_id": "ext-1",
                "title": "Remote updated",
                "updated_at": "2025-06-01T00:00:00",
            },
        ]
    )
    mock_adapter.map_status_outbound = lambda s: s

    with patch("lintel.board_sync_api.sync_engine.get_adapter", return_value=mock_adapter):
        engine = SyncEngine(config_store, mapping_store)
        result = await engine.sync(
            "sc1",
            work_items=[
                {
                    "work_item_id": "wi-1",
                    "title": "Local version",
                    "updated_at": "2025-01-01T00:00:00",
                }
            ],
        )

    assert result["pulled"] == 1
    assert result["skipped"] == 0
    assert result["pulled_items"][0]["title"] == "Remote updated"


async def test_sync_bidirectional_local_wins_skips() -> None:
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    await config_store.add(_make_config(direction=SyncDirection.BIDIRECTIONAL))
    await mapping_store.add(
        {
            "mapping_id": "m1",
            "sync_config_id": "sc1",
            "work_item_id": "wi-1",
            "external_id": "ext-1",
            "last_synced": "",
        }
    )

    mock_adapter = AsyncMock()
    mock_adapter.pull_items = AsyncMock(
        return_value=[
            {"external_id": "ext-1", "title": "Old remote", "updated_at": "2020-01-01T00:00:00"},
        ]
    )
    mock_adapter.map_status_outbound = lambda s: s

    with patch("lintel.board_sync_api.sync_engine.get_adapter", return_value=mock_adapter):
        engine = SyncEngine(config_store, mapping_store)
        result = await engine.sync(
            "sc1",
            work_items=[
                {
                    "work_item_id": "wi-1",
                    "title": "Newer local",
                    "updated_at": "2025-06-01T00:00:00",
                }
            ],
        )

    assert result["pulled"] == 0
    assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


async def test_sync_error_sets_error_status() -> None:
    config_store = BoardSyncConfigStore()
    mapping_store = ExternalIdMappingStore()
    await config_store.add(_make_config(direction=SyncDirection.PULL))

    mock_adapter = AsyncMock()
    mock_adapter.pull_items = AsyncMock(side_effect=RuntimeError("API down"))

    with patch("lintel.board_sync_api.sync_engine.get_adapter", return_value=mock_adapter):
        engine = SyncEngine(config_store, mapping_store)
        result = await engine.sync("sc1", work_items=[])

    assert result["status"] == SyncStatus.ERROR
    config = await config_store.get("sc1")
    assert config is not None
    assert config["status"] == SyncStatus.ERROR
