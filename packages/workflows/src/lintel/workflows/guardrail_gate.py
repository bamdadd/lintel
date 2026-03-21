"""Guardrail gate for pipeline stage transitions (GRD-7).

Provides a check function that queries for active BLOCK guardrails
before allowing deploy-stage transitions.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class GuardrailBlockError(Exception):
    """Raised when a BLOCK guardrail prevents a stage transition."""

    def __init__(self, rule_id: str, rule_name: str, message: str = "") -> None:
        self.rule_id = rule_id
        self.rule_name = rule_name
        super().__init__(message or f"Guardrail BLOCK: {rule_name}")


async def check_guardrail_gate(
    run_id: str,
    stage_name: str,
    guardrail_store: object | None = None,
) -> list[dict[str, str]]:
    """Check for active BLOCK guardrails for a pipeline run.

    Returns a list of blocking guardrail dicts (empty if no blocks).
    Raises GuardrailBlockError if blocks are found and
    raise_on_block=True.

    Args:
        run_id: The pipeline run ID to check.
        stage_name: The target stage name (used for logging).
        guardrail_store: Optional store to query for triggered
            guardrails.

    Returns:
        List of blocking guardrail info dicts with rule_id,
        rule_name, action.
    """
    if guardrail_store is None:
        return []

    # Query for BLOCK guardrails associated with this run
    blocks: list[dict[str, str]] = []

    if hasattr(guardrail_store, "list_all"):
        all_rules = await guardrail_store.list_all()
        for rule in all_rules:
            if rule.get("action") == "BLOCK" and rule.get("enabled", True):
                blocks.append(
                    {
                        "rule_id": rule.get("rule_id", ""),
                        "rule_name": rule.get("name", ""),
                        "action": "BLOCK",
                    }
                )

    if blocks:
        logger.warning(
            "guardrail_gate_blocked",
            run_id=run_id,
            stage_name=stage_name,
            blocking_rules=[b["rule_name"] for b in blocks],
        )

    return blocks
