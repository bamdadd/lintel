"""Auto-improvement loop domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from lintel.workflows.failure_classifier import FailureClass


class ImprovementDecision(StrEnum):
    """Whether an improvement iteration was kept or discarded."""

    KEEP = "keep"
    DISCARD = "discard"
    PENDING = "pending"


class OverfitReason(StrEnum):
    """Reason an improvement was flagged as overfitting."""

    SINGLE_TASK_FIX = "single_task_fix"
    NO_CLASS_IMPROVEMENT = "no_class_improvement"
    REGRESSION = "regression"


@dataclass(frozen=True)
class FailureDistribution:
    """Snapshot of failure class distribution for a set of pipeline runs."""

    total_runs: int = 0
    failed_runs: int = 0
    class_counts: dict[str, int] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return (self.total_runs - self.failed_runs) / self.total_runs

    @property
    def dominant_class(self) -> str:
        if not self.class_counts:
            return FailureClass.UNKNOWN
        return max(self.class_counts, key=lambda k: self.class_counts[k])


@dataclass(frozen=True)
class ImprovementEntry:
    """A single iteration in the improvement ledger.

    Records the before/after pass rates, cost, and whether the
    change was kept or discarded. The ``target_class`` field ensures
    changes target a failure CLASS, not an individual task
    (anti-overfitting rule).
    """

    entry_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    iteration: int = 0
    target_class: str = FailureClass.UNKNOWN
    description: str = ""
    pass_rate_before: float = 0.0
    pass_rate_after: float = 0.0
    cost_usd: float = 0.0
    decision: ImprovementDecision = ImprovementDecision.PENDING
    overfit_reason: str = ""
    failure_distribution_before: dict[str, int] = field(default_factory=dict)
    failure_distribution_after: dict[str, int] = field(default_factory=dict)
    affected_run_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class OverfitCheck:
    """Result of the anti-overfitting validation.

    A change passes if it improves the pass rate for an entire failure
    CLASS, not just for the specific task that triggered the improvement.
    """

    passed: bool = False
    reason: str = ""
    target_class: str = ""
    class_pass_rate_before: float = 0.0
    class_pass_rate_after: float = 0.0
    affected_runs: int = 0
