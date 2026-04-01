"""Agent metrics: accuracy, rework, token efficiency, cost, and step duration.

Implements MET-1 from ``docs/requirements/metrics.md``.  The projection
subscribes to ``AgentStepStarted``, ``AgentStepCompleted``,
``ModelCallCompleted``, ``WorkItemUpdated``, and ``HumanApprovalRejected``
events and maintains running aggregates keyed by agent role.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


# ---------------------------------------------------------------------------
# Read model
# ---------------------------------------------------------------------------


@dataclass
class AgentMetrics:
    """Snapshot of metrics for a single agent role."""

    agent_role: str
    tasks_completed: int = 0
    rework_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    step_count: int = 0

    @property
    def accuracy_score(self) -> float:
        """``(completed - reworked) / completed``.  Returns 1.0 when no tasks."""
        if self.tasks_completed == 0:
            return 1.0
        return max(0.0, (self.tasks_completed - self.rework_count) / self.tasks_completed)

    @property
    def rework_rate(self) -> float:
        """``rework / completed``.  Returns 0.0 when no tasks."""
        if self.tasks_completed == 0:
            return 0.0
        return self.rework_count / self.tasks_completed

    @property
    def token_efficiency(self) -> float:
        """Total tokens per completed task.  Returns 0.0 when no tasks."""
        if self.tasks_completed == 0:
            return 0.0
        return (self.total_input_tokens + self.total_output_tokens) / self.tasks_completed

    @property
    def avg_step_duration_ms(self) -> float:
        """Average wall-clock duration per step in milliseconds."""
        if self.step_count == 0:
            return 0.0
        return self.total_duration_ms / self.step_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_role": self.agent_role,
            "tasks_completed": self.tasks_completed,
            "rework_count": self.rework_count,
            "accuracy_score": round(self.accuracy_score, 4),
            "rework_rate": round(self.rework_rate, 4),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "token_efficiency": round(self.token_efficiency, 2),
            "total_cost_usd": round(self.total_cost_usd, 8),
            "total_duration_ms": self.total_duration_ms,
            "step_count": self.step_count,
            "avg_step_duration_ms": round(self.avg_step_duration_ms, 2),
        }


# ---------------------------------------------------------------------------
# Collector — pure aggregation logic, no I/O
# ---------------------------------------------------------------------------


class AgentMetricsCollector:
    """Stateless helper that applies a single event to an ``AgentMetrics`` instance."""

    @staticmethod
    def apply_step_completed(metrics: AgentMetrics, payload: dict[str, Any]) -> None:
        """Apply an ``AgentStepCompleted`` event payload."""
        metrics.tasks_completed += 1

    @staticmethod
    def apply_model_call(metrics: AgentMetrics, payload: dict[str, Any]) -> None:
        """Apply a ``ModelCallCompleted`` event payload."""
        metrics.total_input_tokens += int(payload.get("input_tokens", 0))
        metrics.total_output_tokens += int(payload.get("output_tokens", 0))
        metrics.total_cost_usd += float(payload.get("cost_usd", 0.0))
        metrics.total_duration_ms += int(payload.get("duration_ms", 0))
        metrics.step_count += 1

    @staticmethod
    def apply_rework(metrics: AgentMetrics) -> None:
        """Record a rework event (rejection or status regression)."""
        metrics.rework_count += 1


# ---------------------------------------------------------------------------
# Status regression helpers
# ---------------------------------------------------------------------------

_STATUS_ORDER: dict[str, int] = {
    "todo": 0,
    "in_progress": 1,
    "in_review": 2,
    "done": 3,
}


def _is_status_regression(old_status: str, new_status: str) -> bool:
    old_idx = _STATUS_ORDER.get(old_status.lower(), -1)
    new_idx = _STATUS_ORDER.get(new_status.lower(), -1)
    if old_idx < 0 or new_idx < 0:
        return False
    return new_idx < old_idx


# ---------------------------------------------------------------------------
# Projection — subscribes to events and maintains per-role read models
# ---------------------------------------------------------------------------


class AgentMetricsProjection:
    """Projection that maintains running ``AgentMetrics`` per agent role.

    Implements the ``Projection`` protocol from ``lintel.projections.protocols``.
    """

    HANDLED_TYPES: frozenset[str] = frozenset(
        {
            "AgentStepCompleted",
            "ModelCallCompleted",
            "HumanApprovalRejected",
            "WorkItemUpdated",
        }
    )

    def __init__(self) -> None:
        self._by_role: dict[str, AgentMetrics] = {}
        self._seen_ids: set[str] = set()
        self._collector = AgentMetricsCollector()

    # -- Projection protocol ------------------------------------------------

    @property
    def name(self) -> str:
        return "agent_metrics"

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    async def project(self, event: EventEnvelope) -> None:
        eid = str(event.event_id)
        if eid in self._seen_ids:
            return
        self._seen_ids.add(eid)

        payload = event.payload
        event_type = event.event_type

        if event_type == "AgentStepCompleted":
            role = payload.get("agent_role", "unknown")
            m = self._ensure_role(role)
            self._collector.apply_step_completed(m, payload)

        elif event_type == "ModelCallCompleted":
            role = payload.get("agent_role", "unknown")
            m = self._ensure_role(role)
            self._collector.apply_model_call(m, payload)

        elif event_type == "HumanApprovalRejected":
            role = payload.get("agent_role", "unknown")
            m = self._ensure_role(role)
            self._collector.apply_rework(m)

        elif event_type == "WorkItemUpdated":
            old_status = payload.get("old_status", "")
            new_status = payload.get("status", payload.get("new_status", ""))
            if _is_status_regression(old_status, new_status):
                role = payload.get("agent_role", "unknown")
                m = self._ensure_role(role)
                self._collector.apply_rework(m)

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._by_role.clear()
        self._seen_ids.clear()
        for event in events:
            if event.event_type in self.HANDLED_TYPES:
                await self.project(event)

    def get_state(self) -> dict[str, Any]:
        return {
            "by_role": {role: m.to_dict() for role, m in self._by_role.items()},
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._by_role.clear()
        self._seen_ids.clear()
        for role, data in state.get("by_role", {}).items():
            m = AgentMetrics(agent_role=role)
            m.tasks_completed = data.get("tasks_completed", 0)
            m.rework_count = data.get("rework_count", 0)
            m.total_input_tokens = data.get("total_input_tokens", 0)
            m.total_output_tokens = data.get("total_output_tokens", 0)
            m.total_cost_usd = data.get("total_cost_usd", 0.0)
            m.total_duration_ms = data.get("total_duration_ms", 0)
            m.step_count = data.get("step_count", 0)
            self._by_role[role] = m

    # -- Query helpers ------------------------------------------------------

    def get_metrics(self, agent_role: str) -> AgentMetrics | None:
        """Return metrics for a single agent role, or ``None``."""
        return self._by_role.get(agent_role)

    def get_all_metrics(self) -> list[AgentMetrics]:
        """Return metrics for all tracked agent roles."""
        return list(self._by_role.values())

    # -- Internal -----------------------------------------------------------

    def _ensure_role(self, role: str) -> AgentMetrics:
        if role not in self._by_role:
            self._by_role[role] = AgentMetrics(agent_role=role)
        return self._by_role[role]
