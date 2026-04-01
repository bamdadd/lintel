"""Slack interactive action handler for approval buttons (REQ-017).

Handles POST /slack/actions from Slack's interactivity webhook.
Parses the action payload, extracts approval_id and decision,
and calls the approval-requests-api resolve endpoint internally.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Form, Request
import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.post("/slack/actions")
async def handle_slack_action(
    request: Request,
    payload: str = Form(...),
) -> dict[str, Any]:
    """Handle Slack interactive component callbacks."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid payload"}

    actions = data.get("actions", [])
    user = data.get("user", {})
    user_id = user.get("id", "unknown")

    for action in actions:
        action_id: str = action.get("action_id", "")
        approval_id = action.get("value", "")

        if action_id.startswith("approval_approve_"):
            approval_id = approval_id or action_id.replace(
                "approval_approve_",
                "",
            )
            await _resolve_approval(
                request,
                approval_id,
                "approve",
                user_id,
            )
        elif action_id.startswith("approval_reject_"):
            approval_id = approval_id or action_id.replace(
                "approval_reject_",
                "",
            )
            await _resolve_approval(
                request,
                approval_id,
                "reject",
                user_id,
            )

    return {"ok": True}


async def _resolve_approval(
    request: Request,
    approval_id: str,
    decision: str,
    user_id: str,
) -> None:
    """Call the approval-requests-api store to resolve."""
    from lintel.approval_requests_api.routes import (
        approval_request_store_provider,
    )
    from lintel.domain.types import ApprovalRequest, ApprovalStatus

    try:
        store = approval_request_store_provider.get()
    except RuntimeError:
        logger.warning("approval_store_not_wired", approval_id=approval_id)
        return

    approval = await store.get(approval_id)
    if approval is None or approval.status != ApprovalStatus.PENDING:
        logger.warning(
            "approval_not_pending",
            approval_id=approval_id,
            status=getattr(approval, "status", None),
        )
        return

    from dataclasses import asdict

    new_status = ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
    updated = ApprovalRequest(
        **{
            **asdict(approval),
            "status": new_status,
            "decided_by": user_id,
        }
    )
    await store.update(updated)

    logger.info(
        "slack_approval_resolved",
        approval_id=approval_id,
        decision=decision,
        user_id=user_id,
    )
