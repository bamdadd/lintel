"""Generate and persist the review report."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger()


async def generate_report(
    state: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Persist the review report and record dimension scores."""
    report_id = str(uuid4())
    repo_id = state.get("repo_id", "")
    aggregated = state.get("aggregated_scores", {})

    logger.info(
        "generate_report.start",
        report_id=report_id,
        repo_id=repo_id,
        scores=aggregated,
    )

    # In a real implementation, this would call review-reports-api and
    # review-scores-api services to persist the report and scores.

    logger.info("generate_report.done", report_id=report_id)
    return {"report_id": report_id}
