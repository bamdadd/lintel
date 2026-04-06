"""Contracts package — shared domain types and protocols."""

from lintel.contracts.channel_adapter import ChannelAdapter
from lintel.contracts.channel_type import ChannelType
from lintel.contracts.concurrency import (
    ConcurrencyState,
    SlotAcquiredEvent,
    SlotReleasedEvent,
)
from lintel.contracts.events import (
    EVENT_TYPE_MAP,
    EventEnvelope,
    deserialize_event,
    register_events,
)
from lintel.contracts.inbound_message import InboundMessage
from lintel.contracts.protocols import (
    CommandDispatcher,
    EventBus,
    EventHandler,
    EventStore,
    EventSubscription,
    SubscriptionHandler,
    SubscriptionToken,
)
from lintel.contracts.protocols.artifact_store import ArtifactRef, ArtifactStore
from lintel.contracts.step_models import (
    NodeType,
    ProjectStepModelOverride,
    StepModelOverrideRequest,
    StepModelOverrideResponse,
)
from lintel.contracts.types import ActorType, CorrelationId, EventId, ThreadRef
from lintel.contracts.work_queue import (
    AgentQueuedEvent,
    WorkQueueEntry,
    WorkQueueStatus,
)

__all__ = [
    "EVENT_TYPE_MAP",
    "ActorType",
    "AgentQueuedEvent",
    "ArtifactRef",
    "ArtifactStore",
    "ChannelAdapter",
    "ChannelType",
    "CommandDispatcher",
    "ConcurrencyState",
    "CorrelationId",
    "EventBus",
    "EventEnvelope",
    "EventHandler",
    "EventId",
    "EventStore",
    "EventSubscription",
    "InboundMessage",
    "NodeType",
    "ProjectStepModelOverride",
    "SlotAcquiredEvent",
    "SlotReleasedEvent",
    "StepModelOverrideRequest",
    "StepModelOverrideResponse",
    "SubscriptionHandler",
    "SubscriptionToken",
    "ThreadRef",
    "WorkQueueEntry",
    "WorkQueueStatus",
    "deserialize_event",
    "register_events",
]
