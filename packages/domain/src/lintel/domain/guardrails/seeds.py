"""Idempotent seed function for default guardrail rules (GRD-7)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.domain.guardrails.repository import RuleRepository

logger = structlog.get_logger()


async def seed_default_guardrails(rule_repo: RuleRepository) -> None:
    """Insert default guardrail rules, skipping any that already exist.

    This function is safe to call on every startup — existing rules
    (including team customisations) are preserved.
    """
    from lintel.domain.guardrails.default_rules import DEFAULT_RULES

    inserted = 0
    skipped = 0

    for rule in DEFAULT_RULES:
        existing = await rule_repo.get(rule.rule_id)
        if existing is not None:
            skipped += 1
            continue
        await rule_repo.upsert(rule)
        inserted += 1

    logger.info(
        "guardrail_seed_complete",
        inserted=inserted,
        skipped=skipped,
        total=len(DEFAULT_RULES),
    )
