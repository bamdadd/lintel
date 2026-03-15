"""Contracts package — shared domain types and protocols."""

from lintel.contracts.concurrency import (
    ConcurrencyState,
    SlotAcquiredEvent,
    SlotReleasedEvent,
)
from lintel.contracts.step_models import (
    NodeType,
    ProjectStepModelOverride,
    StepModelOverrideRequest,
    StepModelOverrideResponse,
)
from lintel.contracts.work_queue import (
    AgentQueuedEvent,
    WorkQueueEntry,
    WorkQueueStatus,
)

__all__ = [
    "AgentQueuedEvent",
    "ConcurrencyState",
    "NodeType",
    "ProjectStepModelOverride",
    "SlotAcquiredEvent",
    "SlotReleasedEvent",
    "StepModelOverrideRequest",
    "StepModelOverrideResponse",
    "WorkQueueEntry",
    "WorkQueueStatus",
]
