"""Observability protocol interfaces."""

from __future__ import annotations

from typing import Protocol


class StepMetricsRecorder(Protocol):
    """Records per-step OTel metrics for workflow execution."""

    def record_step_duration(
        self,
        workflow_id: str,
        step_type: str,
        tool_name: str,
        status: str,
        duration_s: float,
    ) -> None: ...

    def record_step_tokens(
        self,
        workflow_id: str,
        step_type: str,
        model_id: str,
        tokens: int,
    ) -> None: ...
