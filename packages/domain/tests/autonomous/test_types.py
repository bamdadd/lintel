"""Tests for autonomous loop domain types."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.autonomous.types import (
    AutonomousLoop,
    LoopConfig,
    LoopIteration,
    LoopStatus,
)


def test_loop_status_values() -> None:
    assert LoopStatus.IDLE == "idle"
    assert LoopStatus.RUNNING == "running"
    assert LoopStatus.PAUSED == "paused"
    assert LoopStatus.STOPPED == "stopped"


def test_loop_config_defaults() -> None:
    cfg = LoopConfig(loop_id="l1", project_id="p1")
    assert cfg.trigger_interval_seconds == 60
    assert cfg.max_iterations is None
    assert cfg.auto_pick_from_board is True
    assert cfg.filters == {}


def test_loop_iteration_frozen() -> None:
    now = datetime.now(tz=UTC)
    it = LoopIteration(iteration_number=1, started_at=now, outcome="success")
    assert it.iteration_number == 1
    assert it.completed_at is None
    assert it.duration_seconds == 0.0


def test_autonomous_loop_defaults() -> None:
    cfg = LoopConfig(loop_id="l1", project_id="p1")
    loop = AutonomousLoop(loop_id="l1", config=cfg)
    assert loop.status == LoopStatus.IDLE
    assert loop.iterations == ()
    assert loop.current_iteration == 0
