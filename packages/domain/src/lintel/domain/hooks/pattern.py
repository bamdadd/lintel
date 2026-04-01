"""Event pattern matching for workflow hooks.

Supports glob-style patterns using fnmatch:
- ``"*"`` matches all events
- ``"Pipeline*"`` matches PipelineRunStarted, PipelineRunCompleted, etc.
- ``"*Completed"`` matches any event ending with Completed
- ``"WorkItem??eated"`` matches WorkItemCreated (? = single char)
"""

from __future__ import annotations

import fnmatch
from typing import Any


def matches_event_pattern(pattern: str, event_type: str) -> bool:
    """Return True if *event_type* matches the glob *pattern*."""
    if not pattern or pattern == "*":
        return True
    return fnmatch.fnmatch(event_type, pattern)


def conditions_match(conditions: dict[str, object], payload: dict[str, Any]) -> bool:
    """Check all conditions match the event payload (simple equality)."""
    return all(payload.get(key) == expected for key, expected in conditions.items())


def resolve_params(
    template: dict[str, str] | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Resolve ``{{ event.field }}`` placeholders against *payload*."""
    if not template:
        return {}
    result: dict[str, Any] = {}
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            field = value.strip("{ }").replace("event.", "", 1)
            result[key] = payload.get(field, "")
        else:
            result[key] = value
    return result
