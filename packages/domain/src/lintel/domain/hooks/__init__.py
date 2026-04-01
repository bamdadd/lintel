"""Hook system — event pattern matching and hook engine.

Provides HookPreResponse for pre-hook results, match() for glob-style
event pattern matching, and HookEngine for evaluating hooks against events.
"""

from lintel.domain.hooks.matcher import find_matching_hooks, match

__all__ = ["HookPreResponse", "find_matching_hooks", "match"]


from dataclasses import dataclass


@dataclass(frozen=True)
class HookPreResponse:
    """Result of evaluating a pre-hook.

    allow=False blocks the triggering action.
    modified_payload replaces the original event payload when set.
    """

    allow: bool = True
    modified_payload: dict[str, object] | None = None
