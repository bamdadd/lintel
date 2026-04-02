"""Agent gossip and discovery domain model (REQ-034.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class AgentStatus(StrEnum):
    """Status of an agent in the directory."""

    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass(frozen=True)
class AgentAnnouncement:
    """Announcement broadcast by an agent to advertise its presence."""

    agent_id: str
    role: str
    capabilities: list[str]
    status: AgentStatus = AgentStatus.ACTIVE
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class GossipMessage:
    """A message passed between agents via the gossip protocol."""

    sender_id: str
    topic: str
    payload: dict[str, Any]
    ttl: int = 3
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class AgentDirectory:
    """Registry of active agents supporting capability-based discovery."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentAnnouncement] = {}

    def register(self, announcement: AgentAnnouncement) -> None:
        """Register or update an agent in the directory."""
        self._agents[announcement.agent_id] = announcement

    def deregister(self, agent_id: str) -> None:
        """Remove an agent from the directory."""
        self._agents.pop(agent_id, None)

    def discover(self, capability: str) -> list[AgentAnnouncement]:
        """Find all agents that advertise a given capability."""
        return [a for a in self._agents.values() if capability in a.capabilities]

    def get_active(self) -> list[AgentAnnouncement]:
        """Return all agents currently in the directory."""
        return list(self._agents.values())

    def get(self, agent_id: str) -> AgentAnnouncement | None:
        """Look up a single agent by ID."""
        return self._agents.get(agent_id)

    def prune_stale(self, max_age_seconds: float) -> list[str]:
        """Remove agents whose announcement is older than *max_age_seconds*.

        Returns the list of pruned agent IDs.
        """
        now = datetime.now(UTC)
        stale: list[str] = []
        for agent_id, ann in list(self._agents.items()):
            age = (now - ann.timestamp).total_seconds()
            if age > max_age_seconds:
                stale.append(agent_id)
                del self._agents[agent_id]
        return stale


class GossipProtocol:
    """Simple agent-to-agent message passing backed by an AgentDirectory."""

    def __init__(self, directory: AgentDirectory) -> None:
        self._directory = directory
        self._mailboxes: dict[str, list[GossipMessage]] = {}

    def broadcast(self, message: GossipMessage) -> int:
        """Send a message to all active agents (except the sender).

        Returns the number of agents reached.
        """
        if message.ttl <= 0:
            return 0
        agents = self._directory.get_active()
        reached = 0
        for agent in agents:
            if agent.agent_id == message.sender_id:
                continue
            self._mailboxes.setdefault(agent.agent_id, []).append(message)
            reached += 1
        return reached

    def send_to(self, agent_id: str, message: GossipMessage) -> bool:
        """Send a message to a specific agent. Returns False if agent unknown."""
        if self._directory.get(agent_id) is None:
            return False
        self._mailboxes.setdefault(agent_id, []).append(message)
        return True

    def get_messages(self, agent_id: str) -> list[GossipMessage]:
        """Retrieve and drain the message queue for an agent."""
        return self._mailboxes.pop(agent_id, [])
