"""Unit tests for timeout resolution logic."""

from __future__ import annotations

from lintel.workflows.timeout import resolve_timeout
from lintel.workflows.types import StepTimeoutConfig, WorkflowStepConfig


def test_step_level_override_takes_precedence() -> None:
    """Per-step timeout_seconds wins over pipeline and global defaults."""
    step = WorkflowStepConfig(node_name="implement", timeout_seconds=300)
    pipeline = StepTimeoutConfig(default_seconds=600)
    result = resolve_timeout(
        step_config=step,
        pipeline_timeout=pipeline,
        global_default=7200,
    )
    assert result == 300.0


def test_pipeline_level_override_when_no_step_override() -> None:
    """Pipeline-level default_seconds wins when step has no override."""
    step = WorkflowStepConfig(node_name="implement")
    pipeline = StepTimeoutConfig(default_seconds=600)
    result = resolve_timeout(
        step_config=step,
        pipeline_timeout=pipeline,
        global_default=7200,
    )
    assert result == 600.0


def test_global_default_when_no_overrides() -> None:
    """Global default is used when neither step nor pipeline override is set."""
    step = WorkflowStepConfig(node_name="implement")
    assert resolve_timeout(step_config=step, global_default=3600) == 3600.0


def test_fallback_when_nothing_set() -> None:
    """Hard-coded 2-hour fallback when no config is provided."""
    assert resolve_timeout() == 7200.0


def test_none_step_config() -> None:
    """None step_config falls through to pipeline timeout."""
    pipeline = StepTimeoutConfig(default_seconds=900)
    assert resolve_timeout(step_config=None, pipeline_timeout=pipeline) == 900.0


def test_none_pipeline_timeout() -> None:
    """None pipeline_timeout falls through to global default."""
    assert resolve_timeout(pipeline_timeout=None, global_default=1800) == 1800.0


def test_step_timeout_zero_is_valid() -> None:
    """A step timeout of 0 is technically valid (immediate timeout)."""
    step = WorkflowStepConfig(node_name="test", timeout_seconds=0)
    # 0 is falsy but not None — should still be treated as "set"
    # However our implementation checks `is not None`, so 0 should win
    assert resolve_timeout(step_config=step, global_default=7200) == 0.0


def test_returns_float() -> None:
    """Result is always a float regardless of input types."""
    step = WorkflowStepConfig(node_name="test", timeout_seconds=60)
    result = resolve_timeout(step_config=step)
    assert isinstance(result, float)
