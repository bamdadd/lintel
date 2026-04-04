"""In-memory agent metrics store."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentMetricEvent:
    """A single recorded agent productivity metric event."""

    event_id: str
    agent_id: str
    metric_type: str  # "pr_merged" | "lines_changed" | "review_completed"
    value: int = 1
    metadata: dict[str, str] = field(default_factory=dict)
    recorded_at: str = ""


class InMemoryAgentMetricsStore:
    """Simple in-memory store for agent metric events."""

    def __init__(self) -> None:
        self._events: list[AgentMetricEvent] = []

    async def record(self, event: AgentMetricEvent) -> None:
        self._events.append(event)

    async def list_all(self) -> list[AgentMetricEvent]:
        return list(self._events)

    async def summary(self) -> dict[str, dict[str, int]]:
        """Aggregate metrics by agent_id and metric_type."""
        result: dict[str, dict[str, int]] = {}
        for ev in self._events:
            agent = result.setdefault(ev.agent_id, {})
            agent[ev.metric_type] = agent.get(ev.metric_type, 0) + ev.value
        return result

    async def history(
        self,
        agent_id: str | None = None,
        since: str | None = None,
    ) -> list[AgentMetricEvent]:
        """Return events optionally filtered by agent and time."""
        events = self._events
        if agent_id is not None:
            events = [e for e in events if e.agent_id == agent_id]
        if since is not None:
            events = [e for e in events if e.recorded_at >= since]
        return events
