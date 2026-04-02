"""Store protocols for agent prompts and memory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from lintel.domain.agents.types import AgentMemoryEntry, AgentPromptVersion


class AgentPromptStore(Protocol):
    """Versioned prompt store for agents."""

    async def save_version(self, prompt: AgentPromptVersion) -> None:
        """Persist a new prompt version."""
        ...

    async def get_latest(self, agent_id: str) -> AgentPromptVersion | None:
        """Return the latest prompt version for an agent, or None."""
        ...

    async def get_version(self, agent_id: str, version: int) -> AgentPromptVersion | None:
        """Return a specific prompt version, or None."""
        ...

    async def list_versions(self, agent_id: str) -> list[AgentPromptVersion]:
        """Return all prompt versions for an agent, newest first."""
        ...


class AgentMemoryStore(Protocol):
    """Key-value memory store scoped per agent."""

    async def save(self, entry: AgentMemoryEntry) -> None:
        """Save or overwrite a memory entry (keyed by agent_id + key)."""
        ...

    async def get(self, agent_id: str, key: str) -> AgentMemoryEntry | None:
        """Return a single memory entry, or None."""
        ...

    async def list_by_agent(self, agent_id: str) -> list[AgentMemoryEntry]:
        """Return all memory entries for an agent."""
        ...

    async def search(self, agent_id: str, query: str) -> list[AgentMemoryEntry]:
        """Return entries whose key or value contain the query string."""
        ...

    async def delete(self, agent_id: str, key: str) -> bool:
        """Delete an entry. Return True if it existed."""
        ...
