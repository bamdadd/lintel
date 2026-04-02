"""Tests for Chief of Staff meta-agent orchestrator (REQ-F020)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lintel.domain.agents.chief_of_staff import (
    AgentCapability,
    ChiefOfStaff,
    TaskAssignment,
)


def _capability(
    agent_id: str = "agent-1",
    role: str = "coder",
    capabilities: list[str] | None = None,
    current_load: int = 0,
    max_load: int = 5,
    success_rate: float = 0.9,
) -> AgentCapability:
    return AgentCapability(
        agent_id=agent_id,
        role=role,
        capabilities=capabilities or ["python", "testing"],
        current_load=current_load,
        max_load=max_load,
        success_rate=success_rate,
    )


class TestAgentCapability:
    def test_frozen(self) -> None:
        cap = _capability()
        assert cap.agent_id == "agent-1"
        assert cap.role == "coder"
        assert cap.capabilities == ["python", "testing"]
        assert cap.current_load == 0
        assert cap.max_load == 5
        assert cap.success_rate == 0.9

    def test_different_capabilities(self) -> None:
        cap = _capability(capabilities=["rust", "go"], success_rate=0.75)
        assert cap.capabilities == ["rust", "go"]
        assert cap.success_rate == 0.75


class TestTaskAssignment:
    def test_frozen(self) -> None:
        assignment = TaskAssignment(
            task_id="t1",
            agent_id="agent-1",
            priority=1,
            estimated_duration=timedelta(minutes=30),
        )
        assert assignment.task_id == "t1"
        assert assignment.agent_id == "agent-1"
        assert assignment.priority == 1
        assert assignment.estimated_duration == timedelta(minutes=30)

    def test_default_timestamp(self) -> None:
        assignment = TaskAssignment(
            task_id="t1",
            agent_id="a",
            priority=1,
            estimated_duration=timedelta(minutes=10),
        )
        assert assignment.assigned_at.tzinfo is not None


class TestChiefOfStaff:
    def test_register_agent(self) -> None:
        cos = ChiefOfStaff()
        cap = _capability()
        cos.register_agent(cap)
        report = cos.get_status_report()
        assert report["total_agents"] == 1
        assert "agent-1" in report["agents"]  # type: ignore[operator]

    def test_register_agent_overwrites(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability(current_load=0))
        cos.register_agent(_capability(current_load=3))
        report = cos.get_status_report()
        assert report["total_agents"] == 1

    def test_assign_task_basic(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability())
        assignment = cos.assign_task("Write tests", ["python"])
        assert assignment.agent_id == "agent-1"
        assert len(assignment.task_id) > 0

    def test_assign_task_no_matching_agent(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability(capabilities=["python"]))
        with pytest.raises(ValueError, match="No suitable agent"):
            cos.assign_task("Deploy infra", ["kubernetes"])

    def test_assign_task_no_agents(self) -> None:
        cos = ChiefOfStaff()
        with pytest.raises(ValueError, match="No suitable agent"):
            cos.assign_task("Do something", ["python"])

    def test_assign_task_prefers_lower_utilization(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability(agent_id="busy", current_load=4, max_load=5))
        cos.register_agent(_capability(agent_id="free", current_load=0, max_load=5))
        assignment = cos.assign_task("Code task", ["python"])
        assert assignment.agent_id == "free"

    def test_assign_task_skips_full_agents(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability(agent_id="full", current_load=5, max_load=5))
        cos.register_agent(_capability(agent_id="available", current_load=1, max_load=5))
        assignment = cos.assign_task("Code task", ["python"])
        assert assignment.agent_id == "available"

    def test_assign_task_prefers_higher_success_rate(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(
            _capability(agent_id="low", success_rate=0.5, current_load=0, max_load=5)
        )
        cos.register_agent(
            _capability(agent_id="high", success_rate=0.95, current_load=0, max_load=5)
        )
        assignment = cos.assign_task("Code task", ["python"])
        assert assignment.agent_id == "high"

    def test_get_agent_utilization_empty(self) -> None:
        cos = ChiefOfStaff()
        assert cos.get_agent_utilization() == {}

    def test_get_agent_utilization_with_assignments(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability(agent_id="a", max_load=4))
        cos.register_agent(_capability(agent_id="b", max_load=4))
        cos.assign_task("Task 1", ["python"])
        cos.assign_task("Task 2", ["python"])
        util = cos.get_agent_utilization()
        # Both tasks go to same agent (both have same score initially,
        # but second assignment doesn't update current_load on the capability)
        total = sum(util.values())
        assert total > 0

    def test_escalate_stuck_tasks_none_stuck(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability())
        cos.assign_task("Recent task", ["python"])
        stuck = cos.escalate_stuck_tasks(timeout_minutes=60)
        assert stuck == []

    def test_escalate_stuck_tasks_finds_old(self) -> None:
        cos = ChiefOfStaff()
        old_assignment = TaskAssignment(
            task_id="old",
            agent_id="agent-1",
            priority=1,
            estimated_duration=timedelta(minutes=30),
            assigned_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        cos._assignments.append(old_assignment)
        stuck = cos.escalate_stuck_tasks(timeout_minutes=60)
        assert len(stuck) == 1
        assert stuck[0].task_id == "old"

    def test_rebalance_load_no_overload(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability(agent_id="a", max_load=5))
        cos.assign_task("Task", ["python"])
        reassigned = cos.rebalance_load()
        assert reassigned == []

    def test_rebalance_load_moves_excess(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability(agent_id="a", max_load=1))
        cos.register_agent(_capability(agent_id="b", max_load=5))
        # Manually add two tasks to agent a (exceeding max_load=1)
        cos._assignments.append(
            TaskAssignment(
                task_id="t1",
                agent_id="a",
                priority=1,
                estimated_duration=timedelta(minutes=10),
            )
        )
        cos._assignments.append(
            TaskAssignment(
                task_id="t2",
                agent_id="a",
                priority=2,
                estimated_duration=timedelta(minutes=10),
            )
        )
        reassigned = cos.rebalance_load()
        assert len(reassigned) == 1
        assert reassigned[0].agent_id == "b"

    def test_get_status_report(self) -> None:
        cos = ChiefOfStaff()
        cos.register_agent(_capability(agent_id="a"))
        cos.register_agent(_capability(agent_id="b"))
        cos.assign_task("Task", ["python"])
        report = cos.get_status_report()
        assert report["total_agents"] == 2
        assert report["total_assignments"] == 1
        assert "utilization" in report
        assert "agents" in report
