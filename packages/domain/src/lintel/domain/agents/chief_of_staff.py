"""Chief of Staff meta-agent orchestrator (REQ-F020)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import uuid


@dataclass(frozen=True)
class AgentCapability:
    """Describes an agent's role, capabilities, and current workload."""

    agent_id: str
    role: str
    capabilities: list[str]
    current_load: int
    max_load: int
    success_rate: float


@dataclass(frozen=True)
class TaskAssignment:
    """Records a task assigned to a specific agent."""

    task_id: str
    agent_id: str
    priority: int
    estimated_duration: timedelta
    assigned_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ChiefOfStaff:
    """Meta-agent that orchestrates task assignment and load balancing across agents."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentCapability] = {}
        self._assignments: list[TaskAssignment] = []

    def register_agent(self, capability: AgentCapability) -> None:
        """Register or update an agent's capabilities."""
        self._agents[capability.agent_id] = capability

    def assign_task(
        self,
        task_description: str,
        requirements: list[str],
    ) -> TaskAssignment:
        """Assign a task to the best available agent based on requirements and load.

        Selects the agent with the most matching capabilities and lowest utilization.
        Raises ``ValueError`` if no suitable agent is found.
        """
        best_agent: AgentCapability | None = None
        best_score: float = -1.0

        for agent in self._agents.values():
            if agent.current_load >= agent.max_load:
                continue
            matching = sum(1 for r in requirements if r in agent.capabilities)
            if matching == 0:
                continue
            utilization = agent.current_load / agent.max_load if agent.max_load > 0 else 1.0
            score = matching * agent.success_rate * (1.0 - utilization)
            if score > best_score:
                best_score = score
                best_agent = agent

        if best_agent is None:
            msg = "No suitable agent found for the given requirements"
            raise ValueError(msg)

        assignment = TaskAssignment(
            task_id=uuid.uuid4().hex,
            agent_id=best_agent.agent_id,
            priority=1,
            estimated_duration=timedelta(minutes=30),
        )
        self._assignments.append(assignment)
        return assignment

    def rebalance_load(self) -> list[TaskAssignment]:
        """Reassign tasks from overloaded agents. Returns new assignments created."""
        reassigned: list[TaskAssignment] = []
        agent_task_counts: dict[str, int] = {}
        for a in self._assignments:
            agent_task_counts[a.agent_id] = agent_task_counts.get(a.agent_id, 0) + 1

        for agent_id, count in list(agent_task_counts.items()):
            agent = self._agents.get(agent_id)
            if agent is None or count <= agent.max_load:
                continue
            excess = count - agent.max_load
            # Find tasks to reassign (lowest priority first)
            agent_tasks = sorted(
                [t for t in self._assignments if t.agent_id == agent_id],
                key=lambda t: t.priority,
            )
            for task in agent_tasks[:excess]:
                self._assignments.remove(task)
                # Find another agent with capacity
                for candidate in self._agents.values():
                    if candidate.agent_id == agent_id:
                        continue
                    cand_count = agent_task_counts.get(candidate.agent_id, 0)
                    if cand_count < candidate.max_load:
                        new_assignment = TaskAssignment(
                            task_id=task.task_id,
                            agent_id=candidate.agent_id,
                            priority=task.priority,
                            estimated_duration=task.estimated_duration,
                        )
                        self._assignments.append(new_assignment)
                        agent_task_counts[candidate.agent_id] = cand_count + 1
                        agent_task_counts[agent_id] = agent_task_counts[agent_id] - 1
                        reassigned.append(new_assignment)
                        break
        return reassigned

    def get_agent_utilization(self) -> dict[str, float]:
        """Return utilization ratio (0.0-1.0) for each registered agent."""
        task_counts: dict[str, int] = {}
        for a in self._assignments:
            task_counts[a.agent_id] = task_counts.get(a.agent_id, 0) + 1
        return {
            agent_id: task_counts.get(agent_id, 0) / agent.max_load if agent.max_load > 0 else 0.0
            for agent_id, agent in self._agents.items()
        }

    def escalate_stuck_tasks(self, timeout_minutes: int) -> list[TaskAssignment]:
        """Return tasks that have exceeded the timeout duration."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=timeout_minutes)
        return [a for a in self._assignments if a.assigned_at < cutoff]

    def get_status_report(self) -> dict[str, object]:
        """Return a summary of agents, assignments, and utilization."""
        return {
            "total_agents": len(self._agents),
            "total_assignments": len(self._assignments),
            "utilization": self.get_agent_utilization(),
            "agents": list(self._agents.keys()),
        }
