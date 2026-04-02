"""Backwards-compat re-exports — canonical: lintel.domain.skills.discover_test_command."""

from lintel.domain.skills.discover_test_command import (
    SKILL_ID,
    DiscoverTestCommandSkill,
    discover_test_command,
    pick_test_target,
)

__all__ = [
    "SKILL_ID",
    "DiscoverTestCommandSkill",
    "discover_test_command",
    "pick_test_target",
]
