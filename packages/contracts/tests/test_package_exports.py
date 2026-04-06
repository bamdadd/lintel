"""Tests that the contracts package exports all public API from __init__."""

from __future__ import annotations


def test_exports_thread_ref() -> None:
    """ThreadRef is importable from lintel.contracts."""
    from lintel.contracts import ThreadRef

    ref = ThreadRef(workspace_id="w", channel_id="c", thread_ts="t")
    assert ref.workspace_id == "w"


def test_exports_actor_type() -> None:
    """ActorType is importable from lintel.contracts."""
    from lintel.contracts import ActorType

    assert ActorType.HUMAN == "human"
    assert ActorType.AGENT == "agent"
    assert ActorType.SYSTEM == "system"


def test_exports_correlation_id() -> None:
    """CorrelationId is importable from lintel.contracts."""
    from uuid import uuid4

    from lintel.contracts import CorrelationId

    cid = CorrelationId(uuid4())
    assert cid is not None


def test_exports_event_id() -> None:
    """EventId is importable from lintel.contracts."""
    from uuid import uuid4

    from lintel.contracts import EventId

    eid = EventId(uuid4())
    assert eid is not None


def test_exports_event_envelope() -> None:
    """EventEnvelope is importable from lintel.contracts."""
    from lintel.contracts import EventEnvelope

    env = EventEnvelope(event_type="test")
    assert env.event_type == "test"


def test_exports_event_registry() -> None:
    """EVENT_TYPE_MAP, register_events, deserialize_event are importable."""
    from lintel.contracts import EVENT_TYPE_MAP, deserialize_event, register_events

    assert isinstance(EVENT_TYPE_MAP, dict)
    assert callable(register_events)
    assert callable(deserialize_event)


def test_exports_protocols() -> None:
    """Core protocol interfaces are importable from lintel.contracts."""
    from lintel.contracts import (
        CommandDispatcher,
        EventBus,
        EventHandler,
        EventStore,
    )

    # Verify they are Protocol classes
    for proto in (CommandDispatcher, EventBus, EventHandler, EventStore):
        assert hasattr(proto, "__protocol_attrs__")


def test_exports_channel_types() -> None:
    """ChannelAdapter and ChannelType are importable from lintel.contracts."""
    from lintel.contracts import ChannelAdapter, ChannelType

    assert ChannelType is not None
    assert ChannelAdapter is not None


def test_exports_concurrency() -> None:
    """Concurrency types are importable from lintel.contracts."""
    from lintel.contracts import ConcurrencyState, SlotAcquiredEvent, SlotReleasedEvent

    assert ConcurrencyState is not None
    assert SlotAcquiredEvent is not None
    assert SlotReleasedEvent is not None


def test_exports_work_queue() -> None:
    """Work queue types are importable from lintel.contracts."""
    from lintel.contracts import AgentQueuedEvent, WorkQueueEntry, WorkQueueStatus

    assert WorkQueueStatus is not None
    assert WorkQueueEntry is not None
    assert AgentQueuedEvent is not None


def test_all_list_matches_exports() -> None:
    """__all__ contains exactly the exported names."""
    import lintel.contracts as pkg

    all_names = set(pkg.__all__)
    # Every name in __all__ should be importable
    for name in all_names:
        assert hasattr(pkg, name), f"{name} in __all__ but not importable"
