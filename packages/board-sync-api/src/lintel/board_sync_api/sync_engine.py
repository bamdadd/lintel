"""Sync engine — orchestrates pull/push between Lintel and external providers."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lintel.board_sync_api.adapters import get_adapter
from lintel.board_sync_api.types import ConflictStrategy, SyncDirection, SyncStatus

if TYPE_CHECKING:
    from lintel.board_sync_api.store import BoardSyncConfigStore, ExternalIdMappingStore

logger = logging.getLogger(__name__)


def _resolve_conflict(
    local: dict[str, Any],
    remote: dict[str, Any],
    strategy: str,
) -> str:
    """Decide whether the *local* or *remote* version wins.

    Returns ``"local"`` or ``"remote"``.
    """
    if strategy == ConflictStrategy.MANUAL:
        # With manual strategy we skip conflicting items (keep local)
        return "local"

    # last_write_wins (default): compare updated_at timestamps
    local_ts = local.get("updated_at", "")
    remote_ts = remote.get("updated_at", "")
    if remote_ts > local_ts:
        return "remote"
    return "local"


class SyncEngine:
    """Orchestrates bidirectional sync between a board and an external provider."""

    def __init__(
        self,
        config_store: BoardSyncConfigStore,
        mapping_store: ExternalIdMappingStore,
    ) -> None:
        self._config_store = config_store
        self._mapping_store = mapping_store

    async def sync(
        self,
        sync_config_id: str,
        work_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run a sync cycle for the given config.

        Returns a summary dict with counts of pulled/pushed/skipped items
        and the list of pulled items for the caller to upsert.
        """
        config = await self._config_store.get(sync_config_id)
        if config is None:
            msg = f"Sync config not found: {sync_config_id}"
            raise ValueError(msg)

        direction = config.get("direction", SyncDirection.BIDIRECTIONAL)
        provider = config.get("provider", "")
        conflict_strategy = config.get("conflict_strategy", ConflictStrategy.LAST_WRITE_WINS)
        adapter = get_adapter(provider)

        pulled = 0
        pushed = 0
        skipped = 0
        pulled_items: list[dict[str, Any]] = []

        # Mark as syncing
        config["status"] = SyncStatus.SYNCING
        await self._config_store.update(sync_config_id, config)

        try:
            # Pull phase
            if direction in (SyncDirection.PULL, SyncDirection.BIDIRECTIONAL):
                external_items = await adapter.pull_items(config)
                for ext_item in external_items:
                    ext_id = ext_item.get("external_id", "")
                    existing = await self._mapping_store.get_by_external_id(sync_config_id, ext_id)
                    now = datetime.now(UTC).isoformat()

                    if existing is None:
                        # New item from external system — create mapping
                        mapping = {
                            "mapping_id": uuid4().hex,
                            "sync_config_id": sync_config_id,
                            "work_item_id": "",
                            "external_id": ext_id,
                            "last_synced": now,
                        }
                        await self._mapping_store.add(mapping)
                        pulled_items.append(ext_item)
                        pulled += 1
                    elif direction == SyncDirection.BIDIRECTIONAL:
                        # Item exists on both sides — resolve conflict
                        wid = existing.get("work_item_id", "")
                        local = next(
                            (w for w in work_items if w.get("work_item_id") == wid),
                            {},
                        )
                        winner = _resolve_conflict(local, ext_item, conflict_strategy)
                        if winner == "remote":
                            pulled_items.append(ext_item)
                            pulled += 1
                        else:
                            skipped += 1
                        existing["last_synced"] = now
                        await self._mapping_store.update(existing["mapping_id"], existing)
                    else:
                        # Pull-only: always accept remote
                        existing["last_synced"] = now
                        await self._mapping_store.update(existing["mapping_id"], existing)
                        pulled_items.append(ext_item)
                        pulled += 1

            # Push phase
            if direction in (SyncDirection.PUSH, SyncDirection.BIDIRECTIONAL):
                for item in work_items:
                    wid = item.get("work_item_id", "")
                    mapping = await self._mapping_store.get_by_work_item(sync_config_id, wid)
                    now = datetime.now(UTC).isoformat()

                    if mapping is not None:
                        push_item = {
                            **item,
                            "external_id": mapping.get("external_id", ""),
                            "status": adapter.map_status_outbound(item.get("status", "open")),
                        }
                        new_ext_id = await adapter.push_item(config, push_item)
                        mapping["external_id"] = new_ext_id or mapping.get("external_id", "")
                        mapping["last_synced"] = now
                        await self._mapping_store.update(mapping["mapping_id"], mapping)
                        pushed += 1
                    else:
                        # No mapping yet — create in external system and record mapping
                        push_item = {
                            **item,
                            "status": adapter.map_status_outbound(item.get("status", "open")),
                        }
                        new_ext_id = await adapter.push_item(config, push_item)
                        new_mapping = {
                            "mapping_id": uuid4().hex,
                            "sync_config_id": sync_config_id,
                            "work_item_id": wid,
                            "external_id": new_ext_id,
                            "last_synced": now,
                        }
                        await self._mapping_store.add(new_mapping)
                        pushed += 1

            config["status"] = SyncStatus.CONNECTED
            config["last_synced"] = datetime.now(UTC).isoformat()
        except Exception:
            config["status"] = SyncStatus.ERROR
            logger.exception("sync_failed: config=%s", sync_config_id)
        finally:
            await self._config_store.update(sync_config_id, config)

        return {
            "pulled": pulled,
            "pushed": pushed,
            "skipped": skipped,
            "pulled_items": pulled_items,
            "status": config["status"],
        }
