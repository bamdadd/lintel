"""Guardrail event contract types (GRD-7).

Defines the typed shapes for events that the guardrail system produces
and consumes. Actual events flow as EventEnvelope instances with payload
dicts; these dataclasses document the expected payload schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Output events (produced by guardrail engine) ---


@dataclass(frozen=True)
class GuardrailTriggeredPayload:
    """Payload schema for GuardrailTriggered events."""

    rule_id: str = ""
    rule_name: str = ""
    action: str = ""  # WARN, BLOCK, REQUIRE_APPROVAL
    event_type: str = ""
    threshold: float | None = None
    source_event_type: str = ""
    source_payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GuardrailBypassedPayload:
    """Payload schema for GuardrailBypassed events."""

    rule_id: str = ""
    reason: str = ""
    bypassed_by: str = ""


# --- Input event payload schemas (consumed by guardrail engine) ---


@dataclass(frozen=True)
class RunCompletedPayload:
    """Expected payload shape for RunCompleted events."""

    run_id: str = ""
    rework_rate: float = 0.0
    run_cost: float = 0.0


@dataclass(frozen=True)
class SandboxCommandFinishedPayload:
    """Expected payload shape for SandboxCommandFinished events."""

    command_id: str = ""
    duration_seconds: float = 0.0
    status: str = ""


@dataclass(frozen=True)
class TestResultRecordedPayload:
    """Expected payload shape for TestResultRecorded events."""

    run_id: str = ""
    verdict: str = ""  # passed, failed


@dataclass(frozen=True)
class ArtifactCreatedPayload:
    """Expected payload shape for ArtifactCreated events."""

    artifact_id: str = ""
    content_preview: str = ""
    pii_detected: bool = False


@dataclass(frozen=True)
class PullRequestCreatedPayload:
    """Expected payload shape for PullRequestCreated events."""

    pr_id: str = ""
    lines_changed: int = 0
    project_id: str = ""
    project_daily_cost: float = 0.0
