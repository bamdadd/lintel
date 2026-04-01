"""Run-level metrics capture (REQ-034.2.1).

Captures per-run performance metrics such as latency, token usage,
tool call counts, and error rates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True)
class RunMetric:
    """A single metric measurement associated with a pipeline/agent run."""

    metric_id: str = field(default_factory=lambda: str(uuid4()))
    run_id: str = ""
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
