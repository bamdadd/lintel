"""Agent productivity metrics endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider

from .store import AgentMetricEvent, InMemoryAgentMetricsStore

router = APIRouter()

agent_metrics_store_provider: StoreProvider[InMemoryAgentMetricsStore] = StoreProvider()


class RecordMetricRequest(BaseModel):
    """Request body for recording a metric event."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    metric_type: str
    value: int = 1
    metadata: dict[str, str] = Field(default_factory=dict)


@router.get("/agent-metrics/summary")
async def agent_metrics_summary(
    store: InMemoryAgentMetricsStore = Depends(agent_metrics_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """PRs merged, lines changed, reviews completed — grouped by agent."""
    return await store.summary()


@router.get("/agent-metrics/history")
async def agent_metrics_history(
    agent_id: str | None = None,
    since: str | None = None,
    store: InMemoryAgentMetricsStore = Depends(agent_metrics_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """Time-series of metric events, optionally filtered."""
    events = await store.history(agent_id=agent_id, since=since)
    return [
        {
            "event_id": e.event_id,
            "agent_id": e.agent_id,
            "metric_type": e.metric_type,
            "value": e.value,
            "metadata": e.metadata,
            "recorded_at": e.recorded_at,
        }
        for e in events
    ]


@router.post("/agent-metrics/record", status_code=201)
async def record_agent_metric(
    body: RecordMetricRequest,
    store: InMemoryAgentMetricsStore = Depends(agent_metrics_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Log an agent productivity metric event."""
    event = AgentMetricEvent(
        event_id=body.event_id,
        agent_id=body.agent_id,
        metric_type=body.metric_type,
        value=body.value,
        metadata=body.metadata,
        recorded_at=datetime.now(tz=UTC).isoformat(),
    )
    await store.record(event)
    return {
        "event_id": event.event_id,
        "agent_id": event.agent_id,
        "metric_type": event.metric_type,
        "value": event.value,
        "metadata": event.metadata,
        "recorded_at": event.recorded_at,
    }
