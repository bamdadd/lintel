"""Aggregate per-dimension results into unified scores."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def aggregate_scores(
    state: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Combine all dimension analysis results into aggregate scores."""
    per_dimension = state.get("per_dimension_results", {})
    logger.info("aggregate_scores.start", dimensions=list(per_dimension.keys()))

    aggregated: dict[str, float] = {}
    for dimension, result in per_dimension.items():
        if isinstance(result, dict):
            aggregated[dimension] = float(result.get("score", 0.0))

    logger.info("aggregate_scores.done", scores=aggregated)
    return {"aggregated_scores": aggregated}
