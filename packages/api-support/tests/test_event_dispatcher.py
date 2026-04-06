"""Tests for dispatch_event and dispatch_event_raw."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest

from lintel.api_support.event_dispatcher import dispatch_event, dispatch_event_raw
from lintel.contracts.events import EventEnvelope


@dataclass
class _FakeAppState:
    event_store: Any = field(default=None)


class _FakeApp:
    def __init__(self, event_store: Any = None) -> None:
        self.state = _FakeAppState(event_store=event_store)


class _FakeRequest:
    def __init__(self, app: _FakeApp) -> None:
        self.app = app


@pytest.fixture
def event() -> EventEnvelope:
    return EventEnvelope(event_type="test.event")


@pytest.fixture
def mock_store() -> AsyncMock:
    return AsyncMock()


async def test_dispatch_event_appends_to_store(
    event: EventEnvelope,
    mock_store: AsyncMock,
) -> None:
    """dispatch_event calls event_store.append with correct args."""
    request = _FakeRequest(_FakeApp(event_store=mock_store))
    await dispatch_event(request, event, stream_id="test-stream")  # type: ignore[arg-type]

    mock_store.append.assert_awaited_once_with(
        stream_id="test-stream",
        events=[event],
    )


async def test_dispatch_event_default_stream_id(
    event: EventEnvelope,
    mock_store: AsyncMock,
) -> None:
    """dispatch_event defaults to stream_id='admin'."""
    request = _FakeRequest(_FakeApp(event_store=mock_store))
    await dispatch_event(request, event)  # type: ignore[arg-type]

    mock_store.append.assert_awaited_once_with(
        stream_id="admin",
        events=[event],
    )


async def test_dispatch_event_no_event_store(event: EventEnvelope) -> None:
    """dispatch_event silently returns when event_store is None."""
    request = _FakeRequest(_FakeApp(event_store=None))
    await dispatch_event(request, event)  # type: ignore[arg-type]
    # No exception raised


async def test_dispatch_event_swallows_exception(
    event: EventEnvelope,
) -> None:
    """dispatch_event catches exceptions and logs warning."""
    store = AsyncMock()
    store.append.side_effect = RuntimeError("db down")
    request = _FakeRequest(_FakeApp(event_store=store))

    # Should not raise
    await dispatch_event(request, event)  # type: ignore[arg-type]


async def test_dispatch_event_raw_appends_to_store(
    event: EventEnvelope,
    mock_store: AsyncMock,
) -> None:
    """dispatch_event_raw calls event_store.append via app_state."""
    state = _FakeAppState(event_store=mock_store)
    await dispatch_event_raw(state, event, stream_id="raw-stream")

    mock_store.append.assert_awaited_once_with(
        stream_id="raw-stream",
        events=[event],
    )


async def test_dispatch_event_raw_no_event_store(event: EventEnvelope) -> None:
    """dispatch_event_raw silently returns when event_store is None."""
    state = _FakeAppState(event_store=None)
    await dispatch_event_raw(state, event)
    # No exception raised


async def test_dispatch_event_raw_swallows_exception(
    event: EventEnvelope,
) -> None:
    """dispatch_event_raw catches exceptions and logs warning."""
    store = AsyncMock()
    store.append.side_effect = RuntimeError("db down")
    state = _FakeAppState(event_store=store)

    # Should not raise
    await dispatch_event_raw(state, event)
