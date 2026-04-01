"""NotificationDispatcher — subscribes to the event bus and routes notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.domain.notifications.rule_evaluator import NotificationRuleEvaluator

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.domain.notifications.notification_preference import NotificationPreference
    from lintel.domain.notifications.notification_template import NotificationTemplate
    from lintel.domain.notifications.protocols import NotificationService
    from lintel.domain.types import NotificationChannel, NotificationRule

logger = structlog.get_logger()

#: Event types the dispatcher subscribes to.
SUBSCRIBED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "ApprovalRequestCreated",
        "WorkItemCreated",
        "WorkItemUpdated",
        "NotificationSent",
        "GuardrailTriggered",
        "GuardrailEscalated",
        "PipelineRunFailed",
        "PipelineRunCompleted",
    }
)


class NotificationDispatcher:
    """Routes domain events to the correct notification channel.

    Wired at app startup: call ``subscribe_all(event_bus)`` to register
    handlers for all known event types.  When an event is received the
    dispatcher:

    1. Queries matching notification rules from the rule store.
    2. Filters rules by user preferences (default-allow).
    3. Fetches the template for the matched rule/channel combination.
    4. Renders the template with event context and calls the notifier.
    """

    def __init__(
        self,
        notifiers: dict[NotificationChannel, NotificationService],
        rule_store: Any,  # noqa: ANN401  # NotificationRuleStore (avoids hard import from API pkg)
        preference_store: Any,  # noqa: ANN401  # NotificationPreferenceStore
        template_store: Any,  # noqa: ANN401  # NotificationTemplateStore
        evaluator: NotificationRuleEvaluator | None = None,
    ) -> None:
        self._notifiers = notifiers
        self._rule_store = rule_store
        self._preference_store = preference_store
        self._template_store = template_store
        self._evaluator = evaluator or NotificationRuleEvaluator()
        self._subscription_ids: list[str] = []

    # -- EventHandler protocol --------------------------------------------------

    async def handle(self, event: EventEnvelope) -> None:
        """Process a single domain event and dispatch notifications."""
        event_type = event.event_type
        payload: dict[str, Any] = event.payload or {}

        rules: list[NotificationRule] = await self._rule_store.list_all()
        preferences: list[NotificationPreference] = []
        if hasattr(self._preference_store, "list_all"):
            preferences = await self._preference_store.list_all()

        matched = self._evaluator.resolve_rules(event_type, rules, preferences)
        if not matched:
            return

        for rule in matched:
            template_body = self._default_template(event_type)

            # Try to load a stored template for this channel
            if hasattr(self._template_store, "get_by_name_and_channel"):
                tpl: (
                    NotificationTemplate | None
                ) = await self._template_store.get_by_name_and_channel(event_type, rule.channel)
                if tpl is not None:
                    template_body = tpl.body_template

            context: dict[str, str] = {
                "event_type": event_type,
                "recipient": rule.target,
                **{k: str(v) for k, v in payload.items()},
            }
            rendered = template_body.format_map(context)

            notifier = self._notifiers.get(rule.channel)
            if notifier is None:
                logger.warning(
                    "no_notifier_for_channel",
                    channel=str(rule.channel),
                    event_type=event_type,
                )
                continue

            try:
                await notifier.notify(
                    recipient=rule.target,
                    channel=rule.channel,
                    template=rendered,
                    context=context,
                )
            except Exception:
                logger.warning(
                    "notification_dispatch_failed",
                    channel=str(rule.channel),
                    recipient=rule.target,
                    event_type=event_type,
                    exc_info=True,
                )

    # -- Bus subscription helpers -----------------------------------------------

    async def subscribe_all(self, event_bus: Any) -> None:  # noqa: ANN401
        """Register ``self.handle`` for all known notification event types."""
        sub_id: str = await event_bus.subscribe(SUBSCRIBED_EVENT_TYPES, self)
        self._subscription_ids.append(sub_id)
        logger.info(
            "notification_dispatcher_subscribed",
            event_types=sorted(SUBSCRIBED_EVENT_TYPES),
        )

    async def unsubscribe_all(self, event_bus: Any) -> None:  # noqa: ANN401
        """Remove all subscriptions registered via ``subscribe_all``."""
        for sid in self._subscription_ids:
            await event_bus.unsubscribe(sid)
        self._subscription_ids.clear()

    # -- Helpers ----------------------------------------------------------------

    @staticmethod
    def _default_template(event_type: str) -> str:
        """Fallback template when no stored template is found."""
        return f"[{event_type}] Notification for {{recipient}}"
