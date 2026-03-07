"""Typed SSE event dataclasses for real-time run streaming."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamEvent:
    """Base for all SSE events."""

    event_type: str
    step_id: str | None = None
    timestamp_ms: int = 0


@dataclass(frozen=True)
class InitializeStep(StreamEvent):
    event_type: str = "initialize-step"
    step_type: str = ""
    step_name: str = ""
    node_name: str = ""


@dataclass(frozen=True)
class StartStep(StreamEvent):
    event_type: str = "start-step"
    step_type: str = ""


@dataclass(frozen=True)
class FinishStep(StreamEvent):
    event_type: str = "finish-step"
    step_type: str = ""
    status: str = ""
    duration_ms: int = 0


@dataclass(frozen=True)
class ToolCallEvent(StreamEvent):
    event_type: str = "tool-call"
    tool_name: str = ""
    model_id: str = ""
    prompt_preview: str = ""
    tool_input_json: str = ""
    input_tokens: int = 0


@dataclass(frozen=True)
class ToolResultEvent(StreamEvent):
    event_type: str = "tool-result"
    tool_name: str = ""
    output_preview: str = ""
    output_tokens: int = 0
    latency_ms: int = 0
    exit_code: int | None = None


@dataclass(frozen=True)
class LogEvent(StreamEvent):
    event_type: str = "log"
    origin: str = ""
    payload: str = ""


@dataclass(frozen=True)
class StatusEvent(StreamEvent):
    event_type: str = "status"
    status: str = ""


@dataclass(frozen=True)
class EndEvent(StreamEvent):
    event_type: str = "end"
