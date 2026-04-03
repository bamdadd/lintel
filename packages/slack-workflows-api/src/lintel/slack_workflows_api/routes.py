"""Slack workflow invocation CRUD and slash command endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import SlackInvocationReceived
from lintel.domain.types import SlackInvocation
from lintel.slack_workflows_api.store import InMemorySlackInvocationStore  # noqa: TC001

logger = structlog.get_logger()

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


# --- Slash command endpoint ---


@router.post("/slack/commands")
async def handle_slash_command(
    request: Request,
    text: str = Form(default=""),
    command: str = Form(default="/lintel"),
    user_id: str = Form(default=""),
    channel_id: str = Form(default=""),
) -> dict[str, Any]:
    """Handle incoming Slack slash commands (/lintel <subcommand>).

    Slack sends slash commands as application/x-www-form-urlencoded.
    Returns a JSON response with response_type and blocks.
    """
    from lintel.slack.block_kit import build_board_blocks
    from lintel.slack.slash_commands import (
        build_create_response,
        build_error_response,
        build_help_response,
        build_status_response,
        parse_slash_command,
    )

    cmd = parse_slash_command(text)
    logger.info(
        "slash_command_received",
        subcommand=cmd.subcommand,
        user_id=user_id,
        channel_id=channel_id,
    )

    if cmd.subcommand == "help":
        return {"response_type": "ephemeral", "blocks": build_help_response()}

    if cmd.subcommand == "board":
        work_item_store = getattr(request.app.state, "work_item_store", None)
        items = await work_item_store.list_all() if work_item_store else []
        return {"response_type": "ephemeral", "blocks": build_board_blocks(items)}

    if cmd.subcommand == "status":
        if not cmd.args:
            return {
                "response_type": "ephemeral",
                "blocks": build_error_response("Usage: `/lintel status <WORK-ID>`"),
            }
        work_item_store = getattr(request.app.state, "work_item_store", None)
        item = await work_item_store.get(cmd.args.lower()) if work_item_store else None
        return {
            "response_type": "ephemeral",
            "blocks": build_status_response(item, cmd.args),
        }

    if cmd.subcommand == "create":
        parts = cmd.args.split(None, 1)
        valid_types = {"story", "bug", "task", "feature", "refactor"}
        work_type = parts[0].lower() if parts and parts[0].lower() in valid_types else "task"
        title = parts[1] if len(parts) > 1 and parts[0].lower() in valid_types else cmd.args
        if not title.strip():
            return {
                "response_type": "ephemeral",
                "blocks": build_error_response("Usage: `/lintel create [story|bug|task] <title>`"),
            }
        # Map 'story' to 'feature' for domain type
        if work_type == "story":
            work_type = "feature"
        work_item_store = getattr(request.app.state, "work_item_store", None)
        if work_item_store is None:
            return {
                "response_type": "ephemeral",
                "blocks": build_error_response("Work item store not available."),
            }
        from lintel.domain.types import WorkItem

        wi_id = str(uuid4())
        wi = WorkItem(
            work_item_id=wi_id,
            title=title.strip(),
            description="",
            status="open",
            work_type=work_type,
            project_id="",
        )
        await work_item_store.add(wi)
        return {
            "response_type": "in_channel",
            "blocks": build_create_response(title.strip(), work_type, wi_id),
        }

    return {
        "response_type": "ephemeral",
        "blocks": build_error_response(f"Unknown command `{cmd.subcommand}`. Try `/lintel help`."),
    }


# --- Slack interactions (modals / view_submission) ---


@router.post("/slack/interactions")
async def handle_interaction(
    request: Request,
    payload: str = Form(default=""),
) -> dict[str, Any]:
    """Handle Slack interactive payloads (view_submission, block_actions).

    Slack sends interactions as application/x-www-form-urlencoded with a
    JSON-encoded 'payload' field.
    """
    import json

    from lintel.slack.block_kit import parse_view_submission

    try:
        data = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        return {"response_action": "errors", "errors": {"title_block": "Invalid payload"}}

    interaction_type = data.get("type", "")
    logger.info("slack_interaction_received", interaction_type=interaction_type)

    if interaction_type == "view_submission":
        view = data.get("view", {})
        callback_id = view.get("callback_id", "")

        if callback_id == "create_work_item":
            fields = parse_view_submission(view)
            title = fields["title"].strip()
            if not title:
                return {
                    "response_action": "errors",
                    "errors": {"title_block": "Title is required"},
                }

            work_item_store = getattr(request.app.state, "work_item_store", None)
            if work_item_store is None:
                return {
                    "response_action": "errors",
                    "errors": {"title_block": "Work item store not available"},
                }

            from lintel.domain.types import WorkItem

            wi_id = str(uuid4())
            wi = WorkItem(
                work_item_id=wi_id,
                title=title,
                description=fields["description"],
                status="open",
                work_type=fields["work_type"],
                project_id=view.get("private_metadata", ""),
            )
            await work_item_store.add(wi)
            logger.info(
                "work_item_created_via_modal",
                work_item_id=wi_id,
                title=title,
                work_type=fields["work_type"],
            )
            # Return empty response to close the modal
            return {}

    # Unhandled interaction type
    return {}
