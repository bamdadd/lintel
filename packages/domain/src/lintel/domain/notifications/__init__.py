"""Notification routing domain — protocols, entities, and rule evaluation."""

from lintel.domain.notifications.notification_preference import NotificationPreference
from lintel.domain.notifications.notification_template import NotificationTemplate
from lintel.domain.notifications.protocols import NotificationService
from lintel.domain.notifications.rule_evaluator import NotificationRuleEvaluator

__all__ = [
    "NotificationPreference",
    "NotificationRuleEvaluator",
    "NotificationService",
    "NotificationTemplate",
]
