"""In-memory visual verification store."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.visual_verification_api.types import VisualVerification


def _to_dict(v: VisualVerification) -> dict[str, Any]:
    d = asdict(v)
    d["created_at"] = v.created_at.isoformat()
    return d


class InMemoryVisualVerificationStore:
    """Simple in-memory store for visual verifications."""

    def __init__(self) -> None:
        self._items: dict[str, VisualVerification] = {}

    async def add(self, verification: VisualVerification) -> dict[str, Any]:
        self._items[verification.id] = verification
        return _to_dict(verification)

    async def get(self, verification_id: str) -> dict[str, Any] | None:
        v = self._items.get(verification_id)
        if v is None:
            return None
        return _to_dict(v)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_to_dict(v) for v in self._items.values()]

    async def list_by_pipeline(self, pipeline_run_id: str) -> list[dict[str, Any]]:
        return [_to_dict(v) for v in self._items.values() if v.pipeline_run_id == pipeline_run_id]

    async def update(self, verification_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        from lintel.visual_verification_api.types import VisualVerification

        v = self._items.get(verification_id)
        if v is None:
            return None
        data = asdict(v)
        data.update(updates)
        updated = VisualVerification(**data)
        self._items[verification_id] = updated
        return _to_dict(updated)

    async def remove(self, verification_id: str) -> bool:
        if verification_id not in self._items:
            return False
        del self._items[verification_id]
        return True
