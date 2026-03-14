"""Notification dispatcher for workflow phase changes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.api.routes.chat import ChatStore

logger = structlog.get_logger()


class NotificationService:
    """Dispatches phase-change notifications to chat conversations."""

    @staticmethod
    def extract_conversation_id(thread_ref: str) -> str | None:
        """Extract conversation_id from a thread_ref string.

        Thread refs from the chat UI have the format:
        ``thread:lintel-chat:chat:{conversation_id}``
        """
        parts = thread_ref.replace("thread:", "").split(":")
        if len(parts) >= 3 and parts[0] == "lintel-chat":
            return parts[2]
        return None

    @staticmethod
    async def notify_phase_change(
        chat_store: ChatStore | None,
        conversation_id: str,
        phase: str,
        summary: str,
    ) -> None:
        """Add a phase-change notification message to a chat conversation.

        If *chat_store* is ``None`` (e.g. workflow running outside the chat
        context), the call is a no-op — the phase change is still logged so
        external systems can pick it up.
        """
        logger.info(
            "workflow_phase_change",
            conversation_id=conversation_id,
            phase=phase,
            summary=summary,
        )

        if chat_store is None:
            return

        try:
            await chat_store.add_message(
                conversation_id,
                user_id="system",
                display_name="Lintel",
                role="agent",
                content=f"**Phase: {phase}** — {summary}",
            )
        except KeyError:
            logger.warning(
                "notification_conversation_not_found",
                conversation_id=conversation_id,
            )


# Backward-compatible wrappers
def extract_conversation_id(thread_ref: str) -> str | None:
    """Extract conversation_id from a thread_ref string.

    Backward-compatible wrapper around :class:`NotificationService`.
    """
    return NotificationService.extract_conversation_id(thread_ref)


async def notify_phase_change(
    chat_store: ChatStore | None,
    conversation_id: str,
    phase: str,
    summary: str,
) -> None:
    """Add a phase-change notification message to a chat conversation.

    Backward-compatible wrapper around :class:`NotificationService`.
    """
    await NotificationService.notify_phase_change(chat_store, conversation_id, phase, summary)
