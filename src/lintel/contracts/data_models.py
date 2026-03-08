"""Pydantic data models for dict-based stores.

These replace raw dict[str, Any] usage in ChatStore, ProjectStore,
WorkItemStore, AgentDefinitionStore, SandboxStore, and Settings.
Stores can use .model_dump() for serialization and .model_validate()
for deserialization.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """A single message within a conversation."""

    message_id: str
    user_id: str
    display_name: str | None = None
    role: str
    content: str
    timestamp: str = ""


class ConversationData(BaseModel):
    """Full conversation with embedded messages."""

    conversation_id: str
    user_id: str
    display_name: str | None = None
    project_id: str | None = None
    model_id: str | None = None
    created_at: str = ""
    messages: list[ChatMessage] = Field(default_factory=list)


class ConnectionData(BaseModel):
    """External service connection (Slack, GitHub, LLM provider, etc.)."""

    connection_id: str
    connection_type: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "disconnected"


class GeneralSettings(BaseModel):
    """Workspace-level general settings."""

    workspace_name: str = "default"
    default_model_provider: str = ""
    pii_detection_enabled: bool = True
    sandbox_enabled: bool = True
    max_concurrent_workflows: int = 10


class AgentDefinitionData(BaseModel):
    """User-defined agent definition."""

    agent_id: str
    name: str = ""
    description: str = ""
    role: str = ""
    system_prompt: str = ""
    model_id: str = ""
    temperature: float = 0.7
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class SandboxMetadata(BaseModel):
    """Sandbox container metadata."""

    sandbox_id: str
    status: str = "created"
    container_id: str = ""
    image: str = ""
    workspace_path: str = ""
    created_at: str = ""
    repo_url: str = ""
    branch: str = ""

    model_config = ConfigDict(extra="allow")


class ReportVersion(BaseModel):
    """A version entry in stage report history."""

    version: int
    content: str
    editor: str
    type: str = "edit"
    timestamp: str = ""


class CacheStats(BaseModel):
    """Model router cache statistics."""

    hits: int = 0
    misses: int = 0
    size: int = 0


class LLMResponse(BaseModel):
    """Response from a model router call."""

    content: str = ""
    model: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class ProjectData(BaseModel):
    """Project store representation."""

    project_id: str
    name: str = ""
    repo_ids: list[str] = Field(default_factory=list)
    default_branch: str = "main"
    credential_ids: list[str] = Field(default_factory=list)
    status: str = "active"

    model_config = ConfigDict(extra="allow")


class WorkItemData(BaseModel):
    """Work item store representation."""

    work_item_id: str
    project_id: str = ""
    title: str = ""
    description: str = ""
    work_type: str = "task"
    status: str = "open"
    assignee_agent_role: str = ""
    thread_ref_str: str = ""
    branch_name: str = ""
    pr_url: str = ""

    model_config = ConfigDict(extra="allow")


class ThreadStatusData(BaseModel):
    """Thread status projection entry."""

    thread_ref: str
    status: str = "new"
    event_count: int = 0
    last_event_type: str = ""
    last_event_at: str = ""


class TaskBacklogEntry(BaseModel):
    """Task backlog projection entry."""

    correlation_id: str
    thread_ref: str = "unknown"
    status: str = "unknown"
    last_event_at: str = ""
    agent_role: str = ""
    step_name: str = ""
