"""Slack workflow invocation CRUD endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import SlackInvocationReceived
from lintel.domain.types import SlackInvocation
from lintel.slack_workflows_api.store import InMemorySlackInvocationStore  # noqa: TC001

router = APIRouter()

invocation_store_provider: StoreProvider[InMemorySlackInvocationStore] = StoreProvider()


class CreateSlackInvocationRequest(BaseModel):
    slack_channel_id: str
    slack_thread_ts: str
    slack_user_id: str
    prompt: str
    project_id: str
    lintel_user_id: str = ""
    thread_context: list[dict[str, object]] = Field(default_factory=list)
    linked_urls: list[str] = Field(default_factory=list)


@router.post("/slack/invocations", status_code=201)
async def create_invocation(
    request: Request,
    body: CreateSlackInvocationRequest,
    store: Annotated[InMemorySlackInvocationStore, Depends(invocation_store_provider)],
) -> dict[str, Any]:
    invocation_id = str(uuid4())
    invocation = SlackInvocation(
        invocation_id=invocation_id,
        slack_channel_id=body.slack_channel_id,
        slack_thread_ts=body.slack_thread_ts,
        slack_user_id=body.slack_user_id,
        prompt=body.prompt,
        project_id=body.project_id,
        lintel_user_id=body.lintel_user_id,
        thread_context=tuple(body.thread_context),
        linked_urls=tuple(body.linked_urls),
    )
    result = await store.add(invocation)
    await dispatch_event(
        request,
        SlackInvocationReceived(
            payload={
                "resource_id": invocation_id,
                "slack_channel_id": body.slack_channel_id,
                "slack_thread_ts": body.slack_thread_ts,
                "slack_user_id": body.slack_user_id,
                "project_id": body.project_id,
            },
        ),
        stream_id=f"slack-invocation:{invocation_id}",
    )
    return result


@router.get("/slack/invocations")
async def list_invocations(
    store: Annotated[InMemorySlackInvocationStore, Depends(invocation_store_provider)],
    status: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    return await store.list_all(status=status, channel=channel)


@router.get("/slack/invocations/{invocation_id}")
async def get_invocation(
    invocation_id: str,
    store: Annotated[InMemorySlackInvocationStore, Depends(invocation_store_provider)],
) -> dict[str, Any]:
    item = await store.get(invocation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Slack invocation not found")
    return item
