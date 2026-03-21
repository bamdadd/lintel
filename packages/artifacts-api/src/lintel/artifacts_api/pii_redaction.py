"""PII artifact redaction handler (GRD-7).

Subscribes to GuardrailTriggered events where the rule is pii_in_artifacts
and triggers redaction of the affected artifact content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope

logger = structlog.get_logger()


class PIIRedactionHandler:
    """Handles PII BLOCK guardrail events by redacting artifact content."""

    HANDLED_TYPES: frozenset[str] = frozenset({"GuardrailTriggered"})

    def __init__(
        self,
        artifact_store: object | None = None,
    ) -> None:
        self._artifact_store = artifact_store

    async def handle(self, event: EventEnvelope) -> None:
        """Handle a GuardrailTriggered event for pii_in_artifacts rule."""
        payload = event.payload
        rule_name = payload.get("rule_name", "")

        if rule_name != "pii_in_artifacts":
            return

        source_payload = payload.get("source_payload", {})
        if not isinstance(source_payload, dict):
            return

        artifact_id = str(source_payload.get("artifact_id", ""))
        if not artifact_id:
            logger.warning("pii_redaction_no_artifact_id", payload=payload)
            return

        logger.info(
            "pii_redaction_triggered",
            artifact_id=artifact_id,
            rule_name=rule_name,
        )

        # Redact artifact content if store is available
        if self._artifact_store is not None and hasattr(self._artifact_store, "update"):
            await self._artifact_store.update(
                artifact_id,
                {
                    "pii_redacted": True,
                    "content_preview": "[REDACTED - PII detected]",
                },
            )
            logger.info("pii_artifact_redacted", artifact_id=artifact_id)
