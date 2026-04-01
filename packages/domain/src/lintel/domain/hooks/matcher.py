"""Glob-style event pattern matcher for hooks.

Pure functions with no I/O dependencies — easy to unit test.
Uses Python's fnmatch for glob matching (supports *, ?, [seq]).
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.types import Trigger


def match(pattern: str, event_type: str) -> bool:
    """Match an event pattern against an event type.

    Supports exact match and fnmatch globs (*, ?, [seq]).
    Examples:
        match("pipeline.*.completed", "pipeline.build.completed") -> True
        match("Pipeline*", "PipelineRunCompleted") -> True
        match("*.succeeded", "deploy.succeeded") -> True
    """
    if not pattern or pattern == "*":
        return True
    return fnmatch.fnmatch(event_type, pattern)


def find_matching_hooks(
    event_type: str,
    hooks: list[Trigger],
) -> list[Trigger]:
    """Filter hooks whose event_pattern matches the given event type.

    Only considers triggers that have a hook_type and event_pattern set,
    and are enabled.
    """
    results: list[Trigger] = []
    for hook in hooks:
        if not hook.enabled:
            continue
        if hook.hook_type is None or hook.event_pattern is None:
            continue
        if match(hook.event_pattern, event_type):
            results.append(hook)
    return results
