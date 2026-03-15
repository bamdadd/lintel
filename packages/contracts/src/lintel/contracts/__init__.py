"""Contracts package — shared domain types and protocols."""

from lintel.contracts.channel_adapter import ChannelAdapter
from lintel.contracts.channel_type import ChannelType
from lintel.contracts.concurrency import (
    ConcurrencyState,
    SlotAcquiredEvent,
    SlotReleasedEvent,
)
from lintel.contracts.inbound_message import InboundMessage
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
    "ChannelAdapter",
    "ChannelType",
    "ConcurrencyState",
    "InboundMessage",
    "NodeType",
    "ProjectStepModelOverride",
    "SlotAcquiredEvent",
    "SlotReleasedEvent",
    "StepModelOverrideRequest",
    "StepModelOverrideResponse",
    "WorkQueueEntry",
    "WorkQueueStatus",
]
