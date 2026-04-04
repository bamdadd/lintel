"""GitHub App OAuth installation flow and webhook endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import hmac
import os
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import structlog

from lintel.api_support.provider import StoreProvider
from lintel.github_app_api.types import GitHubAppInstallation

if TYPE_CHECKING:
    import httpx

    from lintel.github_app_api.store import InMemoryGitHubAppInstallationStore

logger = structlog.get_logger()

router = APIRouter()

installation_store_provider: StoreProvider[InMemoryGitHubAppInstallationStore] = StoreProvider()
http_client_provider: StoreProvider[httpx.AsyncClient] = StoreProvider()


def _get_app_config() -> dict[str, str]:
    """Read GitHub App config from environment."""
    return {
        "app_id": os.environ.get("GITHUB_APP_ID", ""),
        "client_id": os.environ.get("GITHUB_APP_CLIENT_ID", ""),
        "client_secret": os.environ.get("GITHUB_APP_CLIENT_SECRET", ""),
        "webhook_secret": os.environ.get("GITHUB_APP_WEBHOOK_SECRET", ""),
        "redirect_uri": os.environ.get(
            "GITHUB_APP_REDIRECT_URI",
            "http://localhost:8000/api/v1/integrations/github/callback",
        ),
    }


@router.get("/integrations/github/install")
async def github_install() -> RedirectResponse:
    """Redirect to GitHub App installation page."""
    config = _get_app_config()
    client_id = config["client_id"]
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_APP_CLIENT_ID not configured",
        )
    state = uuid4().hex
    url = (
        f"https://github.com/apps/{os.environ.get('GITHUB_APP_SLUG', 'lintel')}"
        f"/installations/new?state={state}"
    )
    return RedirectResponse(url=url, status_code=302)


class CallbackResponse(BaseModel):
    installation_id: int
    account_login: str
    account_type: str
    id: str


@router.get("/integrations/github/callback")
async def github_callback(
    installation_id: int,
    setup_action: str = "install",
    store: InMemoryGitHubAppInstallationStore = Depends(installation_store_provider),  # noqa: B008
    client: httpx.AsyncClient = Depends(http_client_provider),  # noqa: B008
) -> dict[str, Any]:
    """Handle GitHub App installation callback.

    GitHub redirects here after a user installs/configures the App.
    We fetch the installation details and store them.
    """
    if setup_action == "uninstall":
        existing = await store.get_by_installation_id(installation_id)
        if existing:
            await store.remove(existing.id)
        return {"status": "uninstalled", "installation_id": installation_id}

    # Fetch installation details from GitHub API
    config = _get_app_config()
    app_id = config["app_id"]
    if not app_id:
        raise HTTPException(status_code=500, detail="GITHUB_APP_ID not configured")

    try:
        resp = await client.get(
            f"https://api.github.com/app/installations/{installation_id}",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        gh_data = resp.json()
    except Exception:
        logger.exception("Failed to fetch GitHub installation details")
        gh_data = {}

    account = gh_data.get("account", {})
    record_id = str(uuid4())
    now = datetime.now(UTC).isoformat()

    installation = GitHubAppInstallation(
        id=record_id,
        installation_id=installation_id,
        account_login=account.get("login", "unknown"),
        account_type=account.get("type", "Organization"),
        permissions=gh_data.get("permissions", {}),
        repository_selection=gh_data.get("repository_selection", "all"),
        created_at=now,
        updated_at=now,
    )
    await store.add(installation)

    logger.info(
        "GitHub App installed",
        installation_id=installation_id,
        account=installation.account_login,
    )

    return asdict(installation)


def _verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/integrations/github/webhook")
async def github_webhook(
    request: Request,
    store: InMemoryGitHubAppInstallationStore = Depends(installation_store_provider),  # noqa: B008
) -> dict[str, str]:
    """Handle GitHub App webhook events.

    Processes installation created/deleted events to keep the store in sync.
    """
    config = _get_app_config()
    body = await request.body()

    # Verify signature if webhook secret is configured
    webhook_secret = config["webhook_secret"]
    if webhook_secret:
        signature = request.headers.get("x-hub-signature-256", "")
        if not _verify_webhook_signature(body, signature, webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("x-github-event", "")
    payload = await request.json()
    action = payload.get("action", "")

    logger.info("GitHub webhook received", github_event=event_type, action=action)

    if event_type == "installation":
        await _handle_installation_event(payload, action, store)
    elif event_type == "installation_repositories":
        logger.info(
            "Repository selection changed",
            installation_id=payload.get("installation", {}).get("id"),
        )

    return {"status": "ok"}


async def _handle_installation_event(
    payload: dict[str, Any],
    action: str,
    store: InMemoryGitHubAppInstallationStore,
) -> None:
    """Process installation created/deleted/suspended webhook events."""
    gh_installation = payload.get("installation", {})
    gh_installation_id = gh_installation.get("id", 0)

    if action == "created":
        account = gh_installation.get("account", {})
        now = datetime.now(UTC).isoformat()
        installation = GitHubAppInstallation(
            id=str(uuid4()),
            installation_id=gh_installation_id,
            account_login=account.get("login", "unknown"),
            account_type=account.get("type", "Organization"),
            permissions=gh_installation.get("permissions", {}),
            repository_selection=gh_installation.get("repository_selection", "all"),
            created_at=now,
            updated_at=now,
        )
        await store.add(installation)
        logger.info("Installation created via webhook", installation_id=gh_installation_id)

    elif action == "deleted":
        existing = await store.get_by_installation_id(gh_installation_id)
        if existing:
            await store.remove(existing.id)
            logger.info("Installation deleted via webhook", installation_id=gh_installation_id)

    elif action == "suspended":
        existing = await store.get_by_installation_id(gh_installation_id)
        if existing:
            from dataclasses import replace

            updated = replace(
                existing,
                suspended=True,
                updated_at=datetime.now(UTC).isoformat(),
            )
            await store.update(updated)

    elif action == "unsuspended":
        existing = await store.get_by_installation_id(gh_installation_id)
        if existing:
            from dataclasses import replace

            updated = replace(
                existing,
                suspended=False,
                updated_at=datetime.now(UTC).isoformat(),
            )
            await store.update(updated)
