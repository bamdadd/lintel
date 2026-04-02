"""In-memory trust score store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.trust_scores_api.types import (
    TrustHistory,
    TrustScore,
    _autonomy_tier_for_score,
)


def _score_to_dict(ts: TrustScore) -> dict[str, Any]:
    """Convert a TrustScore dataclass to a JSON-friendly dict."""
    d = asdict(ts)
    d["created_at"] = ts.created_at.isoformat()
    d["updated_at"] = ts.updated_at.isoformat()
    return d


def _history_to_dict(h: TrustHistory) -> dict[str, Any]:
    """Convert a TrustHistory dataclass to a JSON-friendly dict."""
    d = asdict(h)
    d["created_at"] = h.created_at.isoformat()
    d["factor"]["created_at"] = h.factor.created_at.isoformat()
    return d


class InMemoryTrustScoreStore:
    """Simple in-memory store for agent trust scores."""

    def __init__(self) -> None:
        self._scores: dict[str, TrustScore] = {}
        self._history: dict[str, list[TrustHistory]] = {}

    async def get(self, agent_id: str) -> dict[str, Any] | None:
        ts = self._scores.get(agent_id)
        if ts is None:
            return None
        return _score_to_dict(ts)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_score_to_dict(ts) for ts in self._scores.values()]

    async def add(self, trust_score: TrustScore) -> dict[str, Any]:
        self._scores[trust_score.agent_id] = trust_score
        return _score_to_dict(trust_score)

    async def update(self, agent_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        ts = self._scores.get(agent_id)
        if ts is None:
            return None
        data = asdict(ts)
        data.update(updates)
        # Recompute tier from score
        if "score" in updates:
            data["tier"] = _autonomy_tier_for_score(data["score"])
        updated = TrustScore(**data)
        self._scores[agent_id] = updated
        return _score_to_dict(updated)

    async def remove(self, agent_id: str) -> bool:
        if agent_id not in self._scores:
            return False
        del self._scores[agent_id]
        self._history.pop(agent_id, None)
        return True

    async def add_history(self, entry: TrustHistory) -> dict[str, Any]:
        self._history.setdefault(entry.agent_id, []).append(entry)
        return _history_to_dict(entry)

    async def get_history(self, agent_id: str) -> list[dict[str, Any]]:
        entries = self._history.get(agent_id, [])
        return [_history_to_dict(h) for h in entries]
