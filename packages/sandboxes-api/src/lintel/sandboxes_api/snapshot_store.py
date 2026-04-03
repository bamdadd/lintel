"""In-memory store for sandbox session snapshots."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.types import SandboxSnapshot, SandboxSnapshotStatus


def _snapshot_to_dict(snap: SandboxSnapshot) -> dict[str, Any]:
    d = asdict(snap)
    d["created_at"] = snap.created_at.isoformat()
    d["expires_at"] = snap.expires_at.isoformat() if snap.expires_at else None
    return d


class InMemorySnapshotStore:
    """In-memory store for sandbox session snapshots."""

    def __init__(self) -> None:
        self._items: dict[str, SandboxSnapshot] = {}

    async def get(self, snapshot_id: str) -> dict[str, Any] | None:
        item = self._items.get(snapshot_id)
        return _snapshot_to_dict(item) if item else None

    async def list_all(
        self,
        *,
        project_id: str | None = None,
        pipeline_run_id: str | None = None,
        sandbox_id: str | None = None,
        status: SandboxSnapshotStatus | None = None,
    ) -> list[dict[str, Any]]:
        items = (
            s
            for s in self._items.values()
            if (project_id is None or s.project_id == project_id)
            and (pipeline_run_id is None or s.pipeline_run_id == pipeline_run_id)
            and (sandbox_id is None or s.sandbox_id == sandbox_id)
            and (status is None or s.status == status)
        )
        return [
            _snapshot_to_dict(s) for s in sorted(items, key=lambda s: s.created_at, reverse=True)
        ]

    async def add(self, snapshot: SandboxSnapshot) -> dict[str, Any]:
        self._items[snapshot.snapshot_id] = snapshot
        return _snapshot_to_dict(snapshot)

    async def update(
        self,
        snapshot_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        item = self._items.get(snapshot_id)
        if item is None:
            return None
        data = asdict(item)
        data.update(updates)
        updated = SandboxSnapshot(**data)
        self._items[snapshot_id] = updated
        return _snapshot_to_dict(updated)

    async def remove(self, snapshot_id: str) -> bool:
        if snapshot_id not in self._items:
            return False
        del self._items[snapshot_id]
        return True
