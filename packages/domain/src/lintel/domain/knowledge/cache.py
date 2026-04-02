"""Simple in-memory knowledge cache keyed by topic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.knowledge.models import ResearchNode


class KnowledgeCache:
    """In-memory cache mapping topic strings to lists of :class:`ResearchNode`."""

    def __init__(self) -> None:
        self._store: dict[str, list[ResearchNode]] = {}

    def put(self, topic: str, node: ResearchNode) -> None:
        """Cache a node under *topic*."""
        self._store.setdefault(topic, []).append(node)

    def get(self, topic: str) -> list[ResearchNode]:
        """Return cached nodes for *topic*, or empty list."""
        return list(self._store.get(topic, []))

    def search(self, query: str) -> list[ResearchNode]:
        """Return nodes from any topic containing *query* (case-insensitive)."""
        lower = query.lower()
        results: list[ResearchNode] = []
        for key, nodes in self._store.items():
            if lower in key.lower():
                results.extend(nodes)
        return results

    def clear(self) -> None:
        """Remove all cached entries."""
        self._store.clear()

    @property
    def topics(self) -> list[str]:
        """All cached topic keys."""
        return list(self._store.keys())

    def __len__(self) -> int:
        return sum(len(v) for v in self._store.values())
