"""Per-bot Slack OAuth install flow.

Endpoints:
  GET /bots/slack/install?project_id=...  → redirect to Slack OAuth authorize
  GET /bots/slack/oauth/callback          → exchange code, store creds, create SlackBot
"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
import json
import os
import secrets
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx
import structlog

from lintel.api_support.provider import StoreProvider
from lintel.multi_slack_bot_api.store import (
    InMemorySlackBotStore,
    SlackBot,
)

logger = structlog.get_logger()

router = APIRouter()

oauth_slack_bot_store_provider: StoreProvider[InMemorySlackBotStore] = StoreProvider()

SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_DEFAULT_SCOPES = (
    "chat:write,channels:read,channels:history,"
    "groups:read,groups:history,im:read,im:history,users:read"
)


def _get_slack_oauth_config(request: Request) -> dict[str, str]:
    """Read Slack OAuth config from app state or environment."""
    oauth_cfg: dict[str, str] = getattr(request.app.state, "slack_oauth_config", {})
    return {
        "client_id": oauth_cfg.get("client_id", "") or os.environ.get("SLACK_CLIENT_ID", ""),
        "client_secret": oauth_cfg.get("client_secret", "")
        or os.environ.get("SLACK_CLIENT_SECRET", ""),
        "scopes": oauth_cfg.get("scopes", "")
        or os.environ.get("SLACK_OAUTH_SCOPES", SLACK_DEFAULT_SCOPES),
        "redirect_uri": oauth_cfg.get("redirect_uri", "")
        or os.environ.get(
            "SLACK_BOT_OAUTH_REDIRECT_URI",
            os.environ.get("SLACK_OAUTH_REDIRECT_URI", ""),
        ),
    }


def _encode_state(csrf_token: str, project_id: str) -> str:
    """Encode CSRF token and project_id into a single state string."""
    payload = json.dumps({"csrf": csrf_token, "project_id": project_id})
    return urlsafe_b64encode(payload.encode()).decode()


def _decode_state(state: str) -> dict[str, str]:
    """Decode state string back into csrf token and project_id."""
    try:
        payload = urlsafe_b64decode(state.encode()).decode()
        result: dict[str, str] = json.loads(payload)
        return result
    except Exception as exc:
        msg = f"Invalid state encoding: {exc}"
        raise ValueError(msg) from exc


async def _get_credential_store(request: Request) -> object | None:
    return getattr(request.app.state, "credential_store", None)


@router.get("/bots/slack/install")
async def bot_slack_install(
    request: Request,
    project_id: str = "",
) -> RedirectResponse:
    """Redirect to Slack OAuth2 authorize page for per-bot installation."""
    cfg = _get_slack_oauth_config(request)
    if not cfg["client_id"]:
        raise HTTPException(status_code=400, detail="SLACK_CLIENT_ID not configured")

    if not project_id:
        raise HTTPException(status_code=400, detail="project_id query parameter is required")

    csrf_token = secrets.token_urlsafe(32)

    # Store CSRF token for verification in callback
    if not hasattr(request.app.state, "_bot_oauth_states"):
        request.app.state._bot_oauth_states = {}
    request.app.state._bot_oauth_states[csrf_token] = project_id

    state = _encode_state(csrf_token, project_id)

    params: dict[str, str] = {
        "client_id": cfg["client_id"],
        "scope": cfg["scopes"],
        "state": state,
    }
    if cfg["redirect_uri"]:
        params["redirect_uri"] = cfg["redirect_uri"]

    url = f"{SLACK_AUTHORIZE_URL}?{urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/bots/slack/oauth/callback")
async def bot_slack_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    store: InMemorySlackBotStore = Depends(oauth_slack_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Handle Slack OAuth2 callback — exchange code, store creds, create SlackBot."""
    if error:
        raise HTTPException(status_code=400, detail=f"Slack OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")

    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    # Decode and verify state
    try:
        state_data = _decode_state(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state parameter")  # noqa: B904

    csrf_token = state_data.get("csrf", "")
    project_id = state_data.get("project_id", "")

    oauth_states: dict[str, str] = getattr(request.app.state, "_bot_oauth_states", {})
    if not csrf_token or csrf_token not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

    # Consume the state to prevent replay
    del oauth_states[csrf_token]

    if not project_id:
        raise HTTPException(status_code=400, detail="No project_id in state")

    cfg = _get_slack_oauth_config(request)
    if not cfg["client_id"] or not cfg["client_secret"]:
        raise HTTPException(
            status_code=500,
            detail="Slack OAuth client_id/client_secret not configured",
        )

    # Exchange code for token
    token_params: dict[str, str] = {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "code": code,
    }
    if cfg["redirect_uri"]:
        token_params["redirect_uri"] = cfg["redirect_uri"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(SLACK_TOKEN_URL, data=token_params)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=f"Slack token exchange failed: {data.get('error', 'unknown')}",
        )

    bot_token = data.get("access_token", "")
    team_info = data.get("team", {})
    team_id = team_info.get("id", "")
    team_name = team_info.get("name", "")
    bot_user_id = data.get("bot_user_id", "")

    # Store credentials in vault
    credential_store = await _get_credential_store(request)
    bot_id = f"slack-bot-{team_id}-{project_id}"
    credential_id = f"bot:{bot_id}"

    if credential_store is not None:
        combined_secret = f"{bot_token}||||"
        await credential_store.store(  # type: ignore[attr-defined]
            credential_id=credential_id,
            credential_type="slack_bot_token",
            name=f"Slack Bot ({team_name}) - {project_id}",
            secret=combined_secret,
        )

    # Create SlackBot scoped to the project
    slack_bot = SlackBot(
        bot_id=bot_id,
        name=f"Slack Bot ({team_name})",
        workspace_id=team_id,
        bot_token=bot_token,
        scopes=cfg["scopes"].split(","),
        project_bindings=[project_id],
    )
    try:
        await store.add(slack_bot)
    except KeyError:
        # Bot already exists — update token
        await store.update(bot_id, {"bot_token": bot_token, "scopes": cfg["scopes"].split(",")})

    logger.info(
        "bot.oauth.installed",
        bot_id=bot_id,
        team_id=team_id,
        team_name=team_name,
        project_id=project_id,
        bot_user_id=bot_user_id,
    )

    return {
        "ok": True,
        "bot_id": bot_id,
        "project_id": project_id,
        "team_id": team_id,
        "team_name": team_name,
        "bot_user_id": bot_user_id,
    }
