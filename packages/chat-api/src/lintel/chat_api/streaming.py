"""SSE streaming endpoints for chat conversations."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.chat_api.models import SendMessageRequest

from lintel.chat_api.service import ChatService
from lintel.chat_api.store import ChatStore

logger = structlog.get_logger()

streaming_router = APIRouter()


def _get_chat_store(request: Request) -> ChatStore:
    return request.app.state.chat_store  # type: ignore[no-any-return]


_ChatStoreDep = Annotated[ChatStore, Depends(_get_chat_store)]


@streaming_router.post("/chat/conversations/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: str,
    body: SendMessageRequest,
    store: _ChatStoreDep,
    request: Request,
) -> StreamingResponse:
    """Send a message and stream the AI response as SSE."""
    if body.role != "user":
        raise HTTPException(status_code=422, detail="Streaming only supports user messages")
    try:
        await store.add_message(
            conversation_id,
            user_id=body.user_id,
            display_name=body.display_name,
            role=body.role,
            content=body.message,
        )
    except KeyError:
        raise HTTPException(  # noqa: B904
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )

    chat_router = getattr(request.app.state, "chat_router", None)

    effective_model_id = body.model_id
    if effective_model_id is None:
        conv = await store.get(conversation_id)
        if conv is not None:
            effective_model_id = conv.get("model_id")

    svc = ChatService(request, store)
    model_policy, api_base = await svc.resolve_model(effective_model_id)

    async def event_stream() -> AsyncIterator[str]:
        full_content = ""
        workflow_dispatched = False
        if chat_router is None or model_policy is None:
            fallback = "AI responses aren't connected yet. Configure an AI provider."
            yield f"data: {json.dumps({'token': fallback})}\n\n"
            full_content = fallback
        else:
            try:
                result = await chat_router.classify(
                    body.message,
                    model_policy=model_policy,
                    api_base=api_base,
                    enabled_workflows=await svc.get_enabled_workflows(),
                )
                if result.action == "start_workflow":
                    workflow_dispatched = True
                    # Use shared handler (creates work item, pipeline, messages)
                    await svc.handle_classified_message(
                        conversation_id,
                        body.message,
                        result,
                        model_policy,
                        api_base,
                    )
                    # Stream the last agent message back to the client
                    conv_after = await store.get(conversation_id)
                    if conv_after:
                        agent_msgs = [
                            m for m in conv_after.get("messages", []) if m.get("role") == "agent"
                        ]
                        if agent_msgs:
                            full_content = agent_msgs[-1]["content"]
                            yield f"data: {json.dumps({'token': full_content})}\n\n"
                else:
                    # Stream reply token-by-token for chat responses
                    project, repo_url, branch = await svc.resolve_project_context(conversation_id)
                    proj_ctx = svc.build_project_context(project, repo_url, branch)
                    async for token in chat_router.reply_stream(
                        body.message,
                        model_policy=model_policy,
                        api_base=api_base,
                        project_context=proj_ctx,
                    ):
                        full_content += token
                        yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception:
                logger.exception("stream_reply_failed")
                error_msg = "Sorry, I couldn't generate a response right now."
                yield f"data: {json.dumps({'token': error_msg})}\n\n"
                full_content = error_msg

        # Save the complete response (skip if workflow already saved it)
        if full_content and not workflow_dispatched:
            await store.add_message(
                conversation_id,
                user_id="system",
                display_name="Lintel",
                role="agent",
                content=full_content,
            )
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@streaming_router.get("/chat/conversations/{conversation_id}/events")
async def stream_conversation_events(
    conversation_id: str,
    store: _ChatStoreDep,
) -> StreamingResponse:
    """Stream new chat messages via SSE for real-time updates."""
    conv = await store.get(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )

    async def event_stream() -> AsyncIterator[str]:
        last_count = 0
        while True:
            conv = await store.get(conversation_id)
            if conv is None:
                return
            messages = conv.get("messages", [])
            current_count = len(messages)
            if current_count > last_count:
                for msg in messages[last_count:]:
                    yield f"data: {json.dumps(msg)}\n\n"
                last_count = current_count
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
