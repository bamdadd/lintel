"""In-memory knowledge store."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.knowledge_api.types import KnowledgeEntry


class InMemoryKnowledgeStore:
    """Simple in-memory store for knowledge entries with cosine similarity search."""

    def __init__(self) -> None:
        self._entries: dict[str, KnowledgeEntry] = {}

    async def add(self, entry: KnowledgeEntry) -> None:
        self._entries[entry.id] = entry

    async def get(self, entry_id: str) -> KnowledgeEntry | None:
        return self._entries.get(entry_id)

    async def list_all(self, *, project_id: str | None = None) -> list[KnowledgeEntry]:
        entries = list(self._entries.values())
        if project_id is not None:
            entries = [e for e in entries if e.project_id == project_id]
        return entries

    async def update(self, entry: KnowledgeEntry) -> None:
        self._entries[entry.id] = entry

    async def remove(self, entry_id: str) -> None:
        self._entries.pop(entry_id, None)

    async def search(
        self,
        query_embedding: tuple[float, ...],
        *,
        project_id: str | None = None,
        limit: int = 10,
    ) -> list[tuple[KnowledgeEntry, float]]:
        """Return entries ranked by cosine similarity to *query_embedding*."""
        candidates = await self.list_all(project_id=project_id)
        scored: list[tuple[KnowledgeEntry, float]] = []
        for entry in candidates:
            if entry.embedding is None:
                continue
            sim = _cosine_similarity(query_embedding, entry.embedding)
            scored.append((entry, sim))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]


def _cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)
