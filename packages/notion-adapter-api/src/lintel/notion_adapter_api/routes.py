"""Notion adapter API endpoints — connect, sync, and webhook."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.notion_adapter_api.client import NotionAPIError, NotionClient
from lintel.notion_adapter_api.store import InMemoryNotionConnectionStore, NotionConnection
from lintel.notion_adapter_api.sync_engine import pull_work_items, push_work_items
from lintel.notion_adapter_api.webhook import parse_webhook_event, verify_signature

logger = structlog.get_logger(__name__)

router = APIRouter()

notion_connection_store_provider: StoreProvider[InMemoryNotionConnectionStore] = StoreProvider()
webhook_secret_provider: StoreProvider[str] = StoreProvider()


# --------------------------------------------------------------------------
# Request / response models
# --------------------------------------------------------------------------


class ConnectNotionRequest(BaseModel):
    """Payload to register a Notion database connection."""

    connection_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    database_id: str
    api_key: str


class SyncNotionRequest(BaseModel):
    """Payload to trigger a sync operation."""

    connection_id: str
    direction: str = "both"  # push | pull | both
    work_items: list[dict[str, Any]] = Field(default_factory=list)


class NotionWebhookPayload(BaseModel):
    """Incoming Notion webhook payload (simplified)."""

    type: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("/integrations/notion/connections")
async def list_connections(
    project_id: str | None = None,
    store: InMemoryNotionConnectionStore = Depends(notion_connection_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all Notion connections, optionally filtered by project."""
    connections = await store.list_all(project_id=project_id)
    return [
        {
            "connection_id": c.connection_id,
            "project_id": c.project_id,
            "database_id": c.database_id,
            "created_at": c.created_at,
            "last_synced_at": c.last_synced_at,
        }
        for c in connections
    ]


@router.get("/integrations/notion/connections/{connection_id}")
async def get_connection(
    connection_id: str,
    store: InMemoryNotionConnectionStore = Depends(notion_connection_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Retrieve a single Notion connection by ID."""
    connection = await store.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {
        "connection_id": connection.connection_id,
        "project_id": connection.project_id,
        "database_id": connection.database_id,
        "created_at": connection.created_at,
        "last_synced_at": connection.last_synced_at,
    }


@router.delete("/integrations/notion/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    request: Request,
    store: InMemoryNotionConnectionStore = Depends(notion_connection_store_provider),  # noqa: B008
) -> None:
    """Remove a Notion connection."""
    connection = await store.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    await store.remove(connection_id)
    await dispatch_event(
        request,
        {"type": "NotionConnectionDeleted", "payload": {"resource_id": connection_id}},
        stream_id=f"notion_connection:{connection_id}",
    )


@router.post("/integrations/notion/connect", status_code=201)
async def connect_notion(
    body: ConnectNotionRequest,
    request: Request,
    store: InMemoryNotionConnectionStore = Depends(notion_connection_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Register a Notion database connection for a project."""
    existing = await store.get(body.connection_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Connection already exists")

    connection = NotionConnection(
        connection_id=body.connection_id,
        project_id=body.project_id,
        database_id=body.database_id,
        api_key=body.api_key,
    )
    await store.add(connection)
    await dispatch_event(
        request,
        {
            "type": "NotionConnectionCreated",
            "payload": {"resource_id": connection.connection_id},
        },
        stream_id=f"notion_connection:{connection.connection_id}",
    )
    return asdict(connection)


@router.post("/integrations/notion/sync")
async def sync_notion(
    body: SyncNotionRequest,
    request: Request,
    store: InMemoryNotionConnectionStore = Depends(notion_connection_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Trigger a push/pull sync between Lintel work items and a Notion database."""
    connection = await store.get(body.connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        async with NotionClient(api_key=connection.api_key) as client:
            result: dict[str, Any] = {"connection_id": body.connection_id}

            if body.direction in ("push", "both"):
                push_result = await push_work_items(
                    client,
                    connection.database_id,
                    body.work_items,
                )
                result["pushed"] = push_result.pushed
                if push_result.errors:
                    result["push_errors"] = push_result.errors

            if body.direction in ("pull", "both"):
                pull_result = await pull_work_items(client, connection.database_id)
                result["pulled"] = pull_result.pulled
                result["items"] = pull_result.items
                if pull_result.errors:
                    result["pull_errors"] = pull_result.errors
    except NotionAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Update last_synced_at
    updated = NotionConnection(
        connection_id=connection.connection_id,
        project_id=connection.project_id,
        database_id=connection.database_id,
        api_key=connection.api_key,
        created_at=connection.created_at,
        last_synced_at=datetime.now(tz=UTC).isoformat(),
    )
    await store.update(updated)

    await dispatch_event(
        request,
        {"type": "NotionSyncCompleted", "payload": {"resource_id": body.connection_id}},
        stream_id=f"notion_connection:{body.connection_id}",
    )
    return result


@router.post("/integrations/notion/webhook")
async def notion_webhook(
    request: Request,
    store: InMemoryNotionConnectionStore = Depends(notion_connection_store_provider),  # noqa: B008
) -> dict[str, str]:
    """Handle incoming Notion webhook notifications.

    Verifies the webhook signature (when a secret is configured), parses the
    payload to identify the affected database, looks up the matching connection,
    and triggers an incremental pull sync.
    """
    raw_body = await request.body()

    # Signature verification — skip when no secret is configured
    try:
        secret: str | None = webhook_secret_provider.get()
    except RuntimeError:
        secret = None
    if secret:
        sig = request.headers.get("x-notion-signature", "")
        if not sig or not verify_signature(raw_body, sig, secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload: dict[str, Any] = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    event = parse_webhook_event(payload)
    event_type = event["event_type"]
    database_id = event["database_id"]
    page_id = event["page_id"]

    logger.info(
        "notion_webhook_received",
        event_type=event_type,
        page_id=page_id,
        database_id=database_id,
    )

    await dispatch_event(
        request,
        {
            "type": "NotionWebhookReceived",
            "payload": {
                "event_type": event_type,
                "page_id": page_id,
                "database_id": database_id,
            },
        },
        stream_id="notion_webhook",
    )

    # Look up connection by database_id and trigger incremental pull
    if not database_id:
        return {"status": "ignored", "reason": "no database_id in payload"}

    connection = await store.find_by_database_id(database_id)
    if connection is None:
        return {"status": "ignored", "reason": "no matching connection"}

    async with NotionClient(api_key=connection.api_key) as client:
        pull_result = await pull_work_items(client, connection.database_id)

    # Update last_synced_at
    updated = NotionConnection(
        connection_id=connection.connection_id,
        project_id=connection.project_id,
        database_id=connection.database_id,
        api_key=connection.api_key,
        created_at=connection.created_at,
        last_synced_at=datetime.now(tz=UTC).isoformat(),
    )
    await store.update(updated)

    await dispatch_event(
        request,
        {
            "type": "NotionSyncCompleted",
            "payload": {"resource_id": connection.connection_id, "trigger": "webhook"},
        },
        stream_id=f"notion_connection:{connection.connection_id}",
    )

    result: dict[str, str] = {
        "status": "synced",
        "connection_id": connection.connection_id,
        "pulled": str(pull_result.pulled),
    }
    if pull_result.errors:
        result["errors"] = "; ".join(pull_result.errors)
    return result
