"""NotificationRuleEvaluator — filters notification rules against user preferences."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.notifications.notification_preference import NotificationPreference
    from lintel.domain.types import NotificationRule


class NotificationRuleEvaluator:
    """Resolves which notification rules should fire based on user preferences.

    Default-allow: if no preference exists for a user/event/channel combination,
    the rule is included (i.e. notifications are sent unless explicitly disabled).
    """

    @staticmethod
    def resolve_rules(
        event_type: str,
        rules: list[NotificationRule],
        preferences: list[NotificationPreference],
    ) -> list[NotificationRule]:
        """Return rules that match *event_type* and are not disabled by preferences."""
        # Build a lookup: (user_id, event_type, channel) → enabled
        pref_lookup: dict[tuple[str, str, str], bool] = {}
        for pref in preferences:
            pref_lookup[(pref.user_id, pref.event_type, pref.channel)] = pref.enabled

        matched: list[NotificationRule] = []
        for rule in rules:
            if not rule.enabled:
                continue
            if not _rule_matches(rule, event_type):
                continue
            # Check if the target user has explicitly disabled this channel
            key = (rule.target, event_type, rule.channel)
            enabled = pref_lookup.get(key, True)  # default-allow
            if enabled:
                matched.append(rule)

        return matched


def _rule_matches(rule: NotificationRule, event_type: str) -> bool:
    """Return True if *rule* covers *event_type*."""
    if not rule.event_types:
        return True  # empty event_types = wildcard
    for pattern in rule.event_types:
        if pattern == event_type:
            return True
        # Support glob-style wildcard, e.g. "*.timed_out"
        if "*" in pattern:
            import fnmatch

            if fnmatch.fnmatch(event_type, pattern):
                return True
    return False
