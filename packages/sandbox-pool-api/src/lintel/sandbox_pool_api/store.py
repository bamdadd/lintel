"""In-memory stores for sandbox pool resources."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.types import (
    ImageBuildSchedule,
    PooledSandbox,
    SandboxImage,
    SandboxPoolConfig,
    SandboxPoolStatus,
)


def _image_to_dict(img: SandboxImage) -> dict[str, Any]:
    d = asdict(img)
    d["created_at"] = img.created_at.isoformat()
    d["expires_at"] = img.expires_at.isoformat()
    return d


def _sandbox_to_dict(sb: PooledSandbox) -> dict[str, Any]:
    d = asdict(sb)
    d["created_at"] = sb.created_at.isoformat()
    d["last_heartbeat"] = sb.last_heartbeat.isoformat()
    return d


def _config_to_dict(cfg: SandboxPoolConfig) -> dict[str, Any]:
    d = asdict(cfg)
    d["created_at"] = cfg.created_at.isoformat()
    d["updated_at"] = cfg.updated_at.isoformat()
    return d


class InMemorySandboxImageStore:
    """In-memory store for sandbox images."""

    def __init__(self) -> None:
        self._items: dict[str, SandboxImage] = {}

    async def get(self, image_id: str) -> dict[str, Any] | None:
        item = self._items.get(image_id)
        return _image_to_dict(item) if item else None

    async def list_all(self) -> list[dict[str, Any]]:
        return [_image_to_dict(i) for i in self._items.values()]

    async def add(self, image: SandboxImage) -> dict[str, Any]:
        self._items[image.image_id] = image
        return _image_to_dict(image)

    async def remove(self, image_id: str) -> bool:
        if image_id not in self._items:
            return False
        del self._items[image_id]
        return True


class InMemoryPooledSandboxStore:
    """In-memory store for pooled sandboxes."""

    def __init__(self) -> None:
        self._items: dict[str, PooledSandbox] = {}

    async def get(self, sandbox_id: str) -> dict[str, Any] | None:
        item = self._items.get(sandbox_id)
        return _sandbox_to_dict(item) if item else None

    async def list_all(
        self,
        status: SandboxPoolStatus | None = None,
    ) -> list[dict[str, Any]]:
        items = self._items.values()
        if status is not None:
            items = [s for s in items if s.status == status]
        return [_sandbox_to_dict(s) for s in items]

    async def add(self, sandbox: PooledSandbox) -> dict[str, Any]:
        self._items[sandbox.sandbox_id] = sandbox
        return _sandbox_to_dict(sandbox)

    async def update(self, sandbox_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        item = self._items.get(sandbox_id)
        if item is None:
            return None
        data = asdict(item)
        data.update(updates)
        updated = PooledSandbox(**data)
        self._items[sandbox_id] = updated
        return _sandbox_to_dict(updated)

    async def acquire_warm(self, project_id: str) -> dict[str, Any] | None:
        """Find and return a ready sandbox for the given project, or None."""
        for sb in self._items.values():
            if sb.status == SandboxPoolStatus.READY and sb.project_id == project_id:
                return _sandbox_to_dict(sb)
        return None


class InMemorySandboxPoolConfigStore:
    """In-memory store for sandbox pool configs, keyed by project_id."""

    def __init__(self) -> None:
        self._items: dict[str, SandboxPoolConfig] = {}

    async def get(self, project_id: str) -> dict[str, Any] | None:
        item = self._items.get(project_id)
        return _config_to_dict(item) if item else None

    async def upsert(self, config: SandboxPoolConfig) -> dict[str, Any]:
        self._items[config.project_id] = config
        return _config_to_dict(config)


def _schedule_to_dict(sched: ImageBuildSchedule) -> dict[str, Any]:
    d = asdict(sched)
    d["created_at"] = sched.created_at.isoformat()
    d["last_built_at"] = sched.last_built_at.isoformat() if sched.last_built_at else None
    return d


class InMemoryImageBuildScheduleStore:
    """In-memory store for image build schedules."""

    def __init__(self) -> None:
        self._items: dict[str, ImageBuildSchedule] = {}

    async def get(self, schedule_id: str) -> dict[str, Any] | None:
        item = self._items.get(schedule_id)
        return _schedule_to_dict(item) if item else None

    async def list_all(self) -> list[dict[str, Any]]:
        return [_schedule_to_dict(s) for s in self._items.values()]

    async def list_enabled(self) -> list[ImageBuildSchedule]:
        return [s for s in self._items.values() if s.enabled]

    async def add(self, schedule: ImageBuildSchedule) -> dict[str, Any]:
        self._items[schedule.schedule_id] = schedule
        return _schedule_to_dict(schedule)

    async def update(
        self,
        schedule_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        item = self._items.get(schedule_id)
        if item is None:
            return None
        data = asdict(item)
        data.update(updates)
        updated = ImageBuildSchedule(**data)
        self._items[schedule_id] = updated
        return _schedule_to_dict(updated)

    async def remove(self, schedule_id: str) -> bool:
        if schedule_id not in self._items:
            return False
        del self._items[schedule_id]
        return True
