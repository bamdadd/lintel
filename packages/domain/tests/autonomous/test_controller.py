"""Tests for LoopController."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lintel.domain.autonomous.controller import LoopController
from lintel.domain.autonomous.types import LoopConfig, LoopIteration, LoopStatus


@pytest.fixture
def controller() -> LoopController:
    return LoopController()


@pytest.fixture
def config() -> LoopConfig:
    return LoopConfig(loop_id="loop-1", project_id="proj-1", max_iterations=3)


def test_start(controller: LoopController, config: LoopConfig) -> None:
    loop = controller.start(config)
    assert loop.status == LoopStatus.RUNNING
    assert loop.loop_id == "loop-1"


def test_pause_and_resume(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    paused = controller.pause("loop-1")
    assert paused.status == LoopStatus.PAUSED

    resumed = controller.resume("loop-1")
    assert resumed.status == LoopStatus.RUNNING


def test_stop(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    stopped = controller.stop("loop-1")
    assert stopped.status == LoopStatus.STOPPED


def test_pause_non_running_raises(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    controller.pause("loop-1")
    with pytest.raises(ValueError, match="Cannot pause"):
        controller.pause("loop-1")


def test_resume_non_paused_raises(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    with pytest.raises(ValueError, match="Cannot resume"):
        controller.resume("loop-1")


def test_stop_already_stopped_raises(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    controller.stop("loop-1")
    with pytest.raises(ValueError, match="already stopped"):
        controller.stop("loop-1")


def test_get_status(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    loop = controller.get_status("loop-1")
    assert loop.status == LoopStatus.RUNNING


def test_get_unknown_raises(controller: LoopController) -> None:
    with pytest.raises(KeyError, match="not found"):
        controller.get_status("nope")


def test_record_iteration(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    now = datetime.now(tz=UTC)
    it = LoopIteration(iteration_number=1, started_at=now, outcome="success")
    loop = controller.record_iteration("loop-1", it)
    assert len(loop.iterations) == 1
    assert loop.current_iteration == 1


def test_should_continue_running(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    assert controller.should_continue("loop-1") is True


def test_should_continue_paused(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    controller.pause("loop-1")
    assert controller.should_continue("loop-1") is False


def test_should_continue_max_reached(controller: LoopController, config: LoopConfig) -> None:
    controller.start(config)
    now = datetime.now(tz=UTC)
    for i in range(1, 4):
        it = LoopIteration(iteration_number=i, started_at=now, outcome="ok")
        controller.record_iteration("loop-1", it)
    assert controller.should_continue("loop-1") is False


def test_should_continue_no_max(controller: LoopController) -> None:
    cfg = LoopConfig(loop_id="inf", project_id="p1", max_iterations=None)
    controller.start(cfg)
    now = datetime.now(tz=UTC)
    for i in range(1, 100):
        it = LoopIteration(iteration_number=i, started_at=now)
        controller.record_iteration("inf", it)
    assert controller.should_continue("inf") is True
