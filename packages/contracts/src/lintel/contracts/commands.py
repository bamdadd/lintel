"""Command schemas express intent. Commands are imperative and may fail."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef


@dataclass(frozen=True)
class StartWorkflow:
    thread_ref: ThreadRef
    workflow_type: str
    sanitized_messages: tuple[str, ...] = ()
    correlation_id: UUID = field(default_factory=uuid4)
    project_id: str = ""
    work_item_id: str = ""
    run_id: str = ""
    repo_url: str = ""
    repo_urls: tuple[str, ...] = ()
    repo_branch: str = "main"
    credential_ids: tuple[str, ...] = ()
    continue_from_run_id: str = ""
