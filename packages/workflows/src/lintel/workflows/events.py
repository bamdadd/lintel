"""Workflow and pipeline domain events.

Defines events related to workflows, pipelines, and workflow definitions.
Events for hooks, delivery loops, and approvals live in lintel.domain.events.
"""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events

# --- Workflow Events ---


@dataclass(frozen=True)
class IntentRouted(EventEnvelope):
    event_type: str = "IntentRouted"


@dataclass(frozen=True)
class WorkflowStarted(EventEnvelope):
    event_type: str = "WorkflowStarted"


@dataclass(frozen=True)
class WorkflowAdvanced(EventEnvelope):
    event_type: str = "WorkflowAdvanced"


@dataclass(frozen=True)
class WorkflowTriggered(EventEnvelope):
    event_type: str = "WorkflowTriggered"


# --- Pipeline Events ---


@dataclass(frozen=True)
class PipelineRunStarted(EventEnvelope):
    event_type: str = "PipelineRunStarted"


@dataclass(frozen=True)
class PipelineStageCompleted(EventEnvelope):
    event_type: str = "PipelineStageCompleted"


@dataclass(frozen=True)
class PipelineRunCompleted(EventEnvelope):
    event_type: str = "PipelineRunCompleted"


@dataclass(frozen=True)
class PipelineRunFailed(EventEnvelope):
    event_type: str = "PipelineRunFailed"


@dataclass(frozen=True)
class PipelineRunCancelled(EventEnvelope):
    event_type: str = "PipelineRunCancelled"


@dataclass(frozen=True)
class PipelineRunDeleted(EventEnvelope):
    event_type: str = "PipelineRunDeleted"


@dataclass(frozen=True)
class PipelineStageApproved(EventEnvelope):
    event_type: str = "PipelineStageApproved"


@dataclass(frozen=True)
class PipelineStageRejected(EventEnvelope):
    event_type: str = "PipelineStageRejected"


@dataclass(frozen=True)
class PipelineStageRetried(EventEnvelope):
    event_type: str = "PipelineStageRetried"


@dataclass(frozen=True)
class PipelineStageTimedOut(EventEnvelope):
    event_type: str = "PipelineStageTimedOut"


@dataclass(frozen=True)
class StageReportEdited(EventEnvelope):
    event_type: str = "StageReportEdited"


@dataclass(frozen=True)
class StageReportRegenerated(EventEnvelope):
    event_type: str = "StageReportRegenerated"


# --- Workflow Definition Events ---


@dataclass(frozen=True)
class WorkflowDefinitionCreated(EventEnvelope):
    event_type: str = "WorkflowDefinitionCreated"


@dataclass(frozen=True)
class WorkflowDefinitionUpdated(EventEnvelope):
    event_type: str = "WorkflowDefinitionUpdated"


@dataclass(frozen=True)
class WorkflowDefinitionRemoved(EventEnvelope):
    event_type: str = "WorkflowDefinitionRemoved"


# --- Human Interrupt Events (shared by F013, F017, F018) ---


@dataclass(frozen=True)
class HumanInterruptRequested(EventEnvelope):
    event_type: str = "HumanInterruptRequested"


@dataclass(frozen=True)
class HumanInterruptResumed(EventEnvelope):
    event_type: str = "HumanInterruptResumed"


@dataclass(frozen=True)
class HumanInterruptTimedOut(EventEnvelope):
    event_type: str = "HumanInterruptTimedOut"


register_events(
    IntentRouted,
    WorkflowStarted,
    WorkflowAdvanced,
    WorkflowTriggered,
    PipelineRunStarted,
    PipelineStageCompleted,
    PipelineRunCompleted,
    PipelineRunFailed,
    PipelineRunCancelled,
    PipelineRunDeleted,
    PipelineStageApproved,
    PipelineStageRejected,
    PipelineStageRetried,
    PipelineStageTimedOut,
    StageReportEdited,
    StageReportRegenerated,
    WorkflowDefinitionCreated,
    WorkflowDefinitionUpdated,
    WorkflowDefinitionRemoved,
    HumanInterruptRequested,
    HumanInterruptResumed,
    HumanInterruptTimedOut,
)
