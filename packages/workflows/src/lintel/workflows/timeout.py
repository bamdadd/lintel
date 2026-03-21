"""Timeout resolution for pipeline step execution.

Applies three-level precedence:
  1. Per-step override (WorkflowStepConfig.timeout_seconds)
  2. Per-pipeline override (StepTimeoutConfig.default_seconds)
  3. Global default (Settings.default_step_timeout_seconds)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.workflows.types import StepTimeoutConfig, WorkflowStepConfig

# Global fallback when no Settings object is available (2 hours).
_FALLBACK_TIMEOUT_SECONDS: int = 7200


def resolve_timeout(
    step_config: WorkflowStepConfig | None = None,
    pipeline_timeout: StepTimeoutConfig | None = None,
    global_default: int | None = None,
) -> float:
    """Return the effective timeout in seconds for a pipeline step.

    Precedence (first non-None wins):
      1. ``step_config.timeout_seconds`` — per-step override
      2. ``pipeline_timeout.default_seconds`` — per-pipeline override
      3. ``global_default`` — from application settings
      4. ``_FALLBACK_TIMEOUT_SECONDS`` — hard-coded 2-hour fallback
    """
    if step_config is not None and step_config.timeout_seconds is not None:
        return float(step_config.timeout_seconds)

    if pipeline_timeout is not None and pipeline_timeout.default_seconds is not None:
        return float(pipeline_timeout.default_seconds)

    if global_default is not None:
        return float(global_default)

    return float(_FALLBACK_TIMEOUT_SECONDS)
