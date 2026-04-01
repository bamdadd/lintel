"""Fetch recent commits and PR diffs for analysis."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def fetch_commits(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Fetch recent commits and diffs for the target repository."""
    repo_id = state.get("repo_id", "")
    lookback_days = state.get("lookback_days", 7)
    logger.info("fetch_commits.start", repo_id=repo_id, lookback_days=lookback_days)

    # In a real implementation, this would call packages/repos to fetch
    # recent commits and PR diffs. For now, populate state with placeholders.
    commit_shas: list[str] = state.get("commit_shas", [])
    diff_content = state.get("diff_content", "")

    logger.info("fetch_commits.done", commit_count=len(commit_shas))
    return {
        "commit_shas": commit_shas,
        "diff_content": diff_content,
    }
