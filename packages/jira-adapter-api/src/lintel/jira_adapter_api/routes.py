"""Jira adapter REST endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.jira_adapter_api.client import JiraClient
from lintel.jira_adapter_api.sync_engine import run_sync
from lintel.jira_adapter_api.types import (
    JiraConnection,
    SyncDirection,
)

if TYPE_CHECKING:
    from lintel.jira_adapter_api.store import InMemoryJiraConnectionStore, InMemorySyncRecordStore

router = APIRouter()

jira_connection_store_provider: StoreProvider[InMemoryJiraConnectionStore] = StoreProvider()
sync_record_store_provider: StoreProvider[InMemorySyncRecordStore] = StoreProvider()
work_item_store_provider: StoreProvider[Any] = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ConnectJiraRequest(BaseModel):
    connection_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    jira_base_url: str
    jira_project_key: str
    jira_email: str
    api_token: str
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    status_mapping: dict[str, str] = Field(default_factory=dict)


class SyncJiraRequest(BaseModel):
    connection_id: str


class JiraWebhookPayload(BaseModel):
    webhook_event: str = Field(alias="webhookEvent", default="")
    issue: dict[str, Any] = Field(default_factory=dict)
    changelog: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/integrations/jira/connect", status_code=201)
async def connect_jira(
    body: ConnectJiraRequest,
    request: Request,
    store: InMemoryJiraConnectionStore = Depends(jira_connection_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Register a Jira connection for bidirectional sync."""
    existing = await store.get(body.connection_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Connection already exists")
    from datetime import UTC, datetime

    conn = JiraConnection(
        connection_id=body.connection_id,
        project_id=body.project_id,
        jira_base_url=body.jira_base_url,
        jira_project_key=body.jira_project_key,
        jira_email=body.jira_email,
        api_token=body.api_token,
        sync_direction=body.sync_direction,
        status_mapping=body.status_mapping,
        created_at=datetime.now(UTC).isoformat(),
    )
    await store.add(conn)
    result = asdict(conn)
    result.pop("api_token", None)
    return result


@router.post("/integrations/jira/sync")
async def sync_jira(
    body: SyncJiraRequest,
    request: Request,
    conn_store: InMemoryJiraConnectionStore = Depends(  # noqa: B008
        jira_connection_store_provider,
    ),
    sync_store: InMemorySyncRecordStore = Depends(sync_record_store_provider),  # noqa: B008
    wi_store: Any = Depends(work_item_store_provider),  # noqa: ANN401, B008
) -> dict[str, Any]:
    """Trigger a sync for an existing Jira connection."""
    conn = await conn_store.get(body.connection_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    client = JiraClient(
        base_url=conn.jira_base_url,
        email=conn.jira_email,
        api_token=conn.api_token,
    )
    record = await run_sync(conn, client, sync_store, wi_store)
    return asdict(record)


@router.post("/integrations/jira/webhook")
async def jira_webhook(
    body: JiraWebhookPayload,
    request: Request,
    conn_store: InMemoryJiraConnectionStore = Depends(  # noqa: B008
        jira_connection_store_provider,
    ),
) -> dict[str, str]:
    """Handle incoming Jira webhook events (issue created/updated/deleted)."""
    event = body.webhook_event
    issue_key = body.issue.get("key", "")
    project_key = issue_key.split("-")[0] if "-" in issue_key else ""

    connections = await conn_store.list_all()
    matched = [c for c in connections if c.jira_project_key == project_key]

    if not matched:
        return {"status": "ignored", "reason": "no matching connection"}

    return {"status": "accepted", "event": event, "issue_key": issue_key}
