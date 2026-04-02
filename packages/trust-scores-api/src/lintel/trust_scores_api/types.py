"""Agent trust score domain types (REQ-F029)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class AutonomyTier(StrEnum):
    """Oversight level derived from trust score."""

    FULL_AUTONOMY = "full_autonomy"  # 900+
    NORMAL = "normal"  # 700-899
    LIMITED = "limited"  # 500-699
    APPROVAL_REQUIRED = "approval_required"  # 300-499
    SUSPENDED = "suspended"  # 0-299


class TrustFactorKind(StrEnum):
    """Category of trust score adjustment."""

    TASK_SUCCESS = "task_success"
    POLICY_VIOLATION = "policy_violation"
    HUMAN_OVERRIDE = "human_override"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    RECOVERY = "recovery"


def _autonomy_tier_for_score(score: int) -> AutonomyTier:
    """Return the autonomy tier for a given trust score."""
    if score >= 900:
        return AutonomyTier.FULL_AUTONOMY
    if score >= 700:
        return AutonomyTier.NORMAL
    if score >= 500:
        return AutonomyTier.LIMITED
    if score >= 300:
        return AutonomyTier.APPROVAL_REQUIRED
    return AutonomyTier.SUSPENDED


@dataclass(frozen=True)
class TrustFactor:
    """A single trust score adjustment event."""

    factor_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    kind: TrustFactorKind = TrustFactorKind.MANUAL_ADJUSTMENT
    delta: int = 0
    reason: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class TrustScore:
    """Current trust score snapshot for an agent."""

    agent_id: str = ""
    score: int = 500
    tier: AutonomyTier = AutonomyTier.LIMITED
    sponsor: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class TrustHistory:
    """Full trust history entry combining score + factor info."""

    history_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    score_before: int = 0
    score_after: int = 0
    tier_before: AutonomyTier = AutonomyTier.SUSPENDED
    tier_after: AutonomyTier = AutonomyTier.SUSPENDED
    factor: TrustFactor = field(default_factory=TrustFactor)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
