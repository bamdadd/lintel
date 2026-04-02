"""In-memory implementations of agent prompt and memory stores."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.agents.types import AgentMemoryEntry, AgentPromptVersion


class InMemoryAgentPromptStore:
    """In-memory versioned prompt store, keyed by (agent_id, version)."""

    def __init__(self) -> None:
        self._versions: dict[str, list[AgentPromptVersion]] = {}

    async def save_version(self, prompt: AgentPromptVersion) -> None:
        self._versions.setdefault(prompt.agent_id, []).append(prompt)

    async def get_latest(self, agent_id: str) -> AgentPromptVersion | None:
        versions = self._versions.get(agent_id, [])
        if not versions:
            return None
        return max(versions, key=lambda p: p.version)

    async def get_version(self, agent_id: str, version: int) -> AgentPromptVersion | None:
        for p in self._versions.get(agent_id, []):
            if p.version == version:
                return p
        return None

    async def list_versions(self, agent_id: str) -> list[AgentPromptVersion]:
        versions = list(self._versions.get(agent_id, []))
        versions.sort(key=lambda p: p.version, reverse=True)
        return versions


class InMemoryAgentMemoryStore:
    """In-memory agent memory store, keyed by (agent_id, key)."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], AgentMemoryEntry] = {}

    async def save(self, entry: AgentMemoryEntry) -> None:
        self._entries[(entry.agent_id, entry.key)] = entry

    async def get(self, agent_id: str, key: str) -> AgentMemoryEntry | None:
        entry = self._entries.get((agent_id, key))
        if entry is None:
            return None
        if entry.expires_at and entry.expires_at <= datetime.now(UTC):
            del self._entries[(agent_id, key)]
            return None
        return entry

    async def list_by_agent(self, agent_id: str) -> list[AgentMemoryEntry]:
        now = datetime.now(UTC)
        result: list[AgentMemoryEntry] = []
        expired_keys: list[tuple[str, str]] = []
        for (aid, key), entry in self._entries.items():
            if aid != agent_id:
                continue
            if entry.expires_at and entry.expires_at <= now:
                expired_keys.append((aid, key))
                continue
            result.append(entry)
        for k in expired_keys:
            del self._entries[k]
        return result

    async def search(self, agent_id: str, query: str) -> list[AgentMemoryEntry]:
        now = datetime.now(UTC)
        q = query.lower()
        result: list[AgentMemoryEntry] = []
        for (aid, _key), entry in self._entries.items():
            if aid != agent_id:
                continue
            if entry.expires_at and entry.expires_at <= now:
                continue
            if q in entry.key.lower() or q in entry.value.lower():
                result.append(entry)
        return result

    async def delete(self, agent_id: str, key: str) -> bool:
        return self._entries.pop((agent_id, key), None) is not None
