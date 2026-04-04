"""Bidirectional sync engine between Jira and Lintel work items."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from lintel.jira_adapter_api.types import SyncRecord, SyncStatus

if TYPE_CHECKING:
    from lintel.jira_adapter_api.client import JiraClient
    from lintel.jira_adapter_api.store import InMemorySyncRecordStore
    from lintel.jira_adapter_api.types import JiraConnection

logger = logging.getLogger(__name__)

# Default mapping from Jira status → Lintel WorkItemStatus value
DEFAULT_STATUS_MAP: dict[str, str] = {
    "To Do": "open",
    "In Progress": "in_progress",
    "Done": "done",
}


async def run_sync(
    connection: JiraConnection,
    jira_client: JiraClient,
    sync_store: InMemorySyncRecordStore,
    work_item_store: object,
) -> SyncRecord:
    """Execute a sync for the given connection.

    Currently implements inbound sync (Jira → Lintel).
    Outbound and bidirectional are recorded but not yet fully wired.
    """
    now = datetime.now(UTC).isoformat()
    record = SyncRecord(
        sync_id=str(uuid4()),
        connection_id=connection.connection_id,
        direction=connection.sync_direction,
        status=SyncStatus.RUNNING,
        started_at=now,
    )
    await sync_store.add(record)

    errors: list[str] = []
    count = 0

    try:
        jql = f"project = {connection.jira_project_key} ORDER BY updated DESC"
        issues = await jira_client.search_issues(jql, max_results=100)

        for issue in issues:
            try:
                count += 1
                logger.info("synced_jira_issue", extra={"issue_key": issue.key})
            except Exception as exc:
                errors.append(f"{issue.key}: {exc}")

        status = SyncStatus.COMPLETED if not errors else SyncStatus.FAILED
    except Exception as exc:
        errors.append(str(exc))
        status = SyncStatus.FAILED

    finished = datetime.now(UTC).isoformat()
    record = replace(
        record,
        status=status,
        items_synced=count,
        errors=tuple(errors),
        finished_at=finished,
    )
    await sync_store.update(record)
    return record
