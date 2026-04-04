"""Tests for sync engine."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from lintel.jira_adapter_api.store import InMemorySyncRecordStore
from lintel.jira_adapter_api.sync_engine import run_sync
from lintel.jira_adapter_api.types import (
    JiraConnection,
    JiraIssue,
    SyncStatus,
)


@pytest.fixture()
def connection() -> JiraConnection:
    return JiraConnection(
        connection_id="conn-1",
        project_id="proj-1",
        jira_base_url="https://example.atlassian.net",
        jira_project_key="EX",
        jira_email="user@example.com",
        api_token="token",
    )


async def test_sync_completes_on_success(connection: JiraConnection) -> None:
    client = AsyncMock()
    client.search_issues.return_value = [
        JiraIssue(key="EX-1", summary="Issue 1", status="To Do", issue_type="Task"),
    ]
    sync_store = InMemorySyncRecordStore()
    record = await run_sync(connection, client, sync_store, object())
    assert record.status == SyncStatus.COMPLETED
    assert record.items_synced == 1
    assert record.errors == ()


async def test_sync_fails_on_client_error(connection: JiraConnection) -> None:
    client = AsyncMock()
    client.search_issues.side_effect = RuntimeError("network error")
    sync_store = InMemorySyncRecordStore()
    record = await run_sync(connection, client, sync_store, object())
    assert record.status == SyncStatus.FAILED
    assert "network error" in record.errors[0]
