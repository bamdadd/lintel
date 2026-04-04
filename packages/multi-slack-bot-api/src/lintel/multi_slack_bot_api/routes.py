"""Slack bot CRUD endpoints and webhook dispatcher."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

from lintel.api_support.provider import StoreProvider
from lintel.multi_slack_bot_api.store import SlackBot

if TYPE_CHECKING:
    from lintel.multi_slack_bot_api.store import InMemorySlackBotStore

logger = structlog.get_logger()

router = APIRouter()

slack_bot_store_provider: StoreProvider[InMemorySlackBotStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateSlackBotRequest(BaseModel):
    bot_id: str | None = None
    name: str
    workspace_id: str
    bot_token: str
    signing_secret: str = ""
    app_id: str = ""
    scopes: list[str] = Field(default_factory=list)
    project_bindings: list[str] = Field(default_factory=list)
    workflow_bindings: list[str] = Field(default_factory=list)
    channel_bindings: list[str] = Field(default_factory=list)


class UpdateSlackBotRequest(BaseModel):
    name: str | None = None
    signing_secret: str | None = None
    scopes: list[str] | None = None
    project_bindings: list[str] | None = None
    workflow_bindings: list[str] | None = None
    channel_bindings: list[str] | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Signing-secret verification
# ---------------------------------------------------------------------------

SLACK_SIGNATURE_VERSION = "v0"
MAX_TIMESTAMP_DRIFT_SECONDS = 300


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """Verify a Slack request signature using HMAC-SHA256."""
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    if abs(time.time() - ts) > MAX_TIMESTAMP_DRIFT_SECONDS:
        return False
    sig_basestring = f"{SLACK_SIGNATURE_VERSION}:{timestamp}:{body.decode('utf-8')}"
    computed = (
        f"{SLACK_SIGNATURE_VERSION}="
        + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(computed, signature)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/slack-bots", status_code=201)
async def create_slack_bot(
    body: CreateSlackBotRequest,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    bot = SlackBot(
        name=body.name,
        workspace_id=body.workspace_id,
        bot_token=body.bot_token,
        signing_secret=body.signing_secret,
        app_id=body.app_id,
        scopes=body.scopes,
        project_bindings=body.project_bindings,
        workflow_bindings=body.workflow_bindings,
        channel_bindings=body.channel_bindings,
        **({"bot_id": body.bot_id} if body.bot_id else {}),
    )
    try:
        await store.add(bot)
    except KeyError:
        raise HTTPException(status_code=409, detail="Slack bot already exists")  # noqa: B904
    return _safe_dict(bot)


@router.get("/slack-bots")
async def list_slack_bots(
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    bots = await store.list_all(workspace_id=workspace_id)
    return [_safe_dict(b) for b in bots]


@router.get("/slack-bots/{bot_id}")
async def get_slack_bot(
    bot_id: str,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    bot = await store.get(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Slack bot not found")
    return _safe_dict(bot)


@router.patch("/slack-bots/{bot_id}")
async def update_slack_bot(
    bot_id: str,
    body: UpdateSlackBotRequest,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    updated = await store.update(bot_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Slack bot not found")
    return _safe_dict(updated)


@router.delete("/slack-bots/{bot_id}", status_code=204)
async def delete_slack_bot(
    bot_id: str,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> None:
    removed = await store.remove(bot_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Slack bot not found")


# ---------------------------------------------------------------------------
# Webhook dispatcher — shared endpoint that disambiguates by signing secret
# ---------------------------------------------------------------------------


@router.post("/slack-bots/webhook")
async def slack_bot_webhook(
    request: Request,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Receive Slack events and route to the correct bot by signing secret.

    Slack sends ``X-Slack-Signature`` and ``X-Slack-Request-Timestamp``
    headers.  We iterate over registered bots and verify against each
    bot's signing secret to find the owner.
    """
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Handle Slack URL verification challenge (no signature check needed)
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")  # noqa: B904

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # Find the bot whose signing secret matches
    bots = await store.list_all()
    matched_bot: SlackBot | None = None
    for bot in bots:
        if not bot.enabled or not bot.signing_secret:
            continue
        if verify_slack_signature(bot.signing_secret, timestamp, body, signature):
            matched_bot = bot
            break

    if matched_bot is None:
        raise HTTPException(status_code=401, detail="No bot matched the request signature")

    logger.info(
        "slack_bot.webhook.dispatched",
        bot_id=matched_bot.bot_id,
        bot_name=matched_bot.name,
        event_type=payload.get("event", {}).get("type", "unknown"),
    )

    return {
        "ok": True,
        "bot_id": matched_bot.bot_id,
        "bot_name": matched_bot.name,
        "event_type": payload.get("event", {}).get("type", "unknown"),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_dict(bot: SlackBot) -> dict[str, Any]:
    """Convert a SlackBot to a dict, masking the signing secret."""
    d = asdict(bot)
    if d.get("signing_secret"):
        d["signing_secret"] = "***"
    return d
