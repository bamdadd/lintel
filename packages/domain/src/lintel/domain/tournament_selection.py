"""Tournament selection via UCB1 algorithm (REQ-034.2.3).

Pure-function module implementing multi-armed bandit selection for
strategy tournaments and round-robin scheduling for cold-start seeding.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.evolutionary_strategy import (
        EvolutionaryStrategy,
        StrategyScore,
    )


def select_variant(
    variants: list[StrategyScore],
    exploration_constant: float = 1.414,
) -> EvolutionaryStrategy:
    """Select the next strategy to try using UCB1.

    UCB1 balances exploitation (high win rate) with exploration
    (under-tested strategies).  Falls back to round-robin when
    no variants have been tested yet.

    Parameters
    ----------
    variants:
        List of strategies with their win/loss records.
    exploration_constant:
        Controls exploration vs exploitation tradeoff (sqrt(2) by default).

    Returns
    -------
    The strategy with the highest UCB1 score.

    Raises
    ------
    ValueError
        If *variants* is empty.
    """
    if not variants:
        msg = "variants must not be empty"
        raise ValueError(msg)

    if len(variants) == 1:
        return variants[0].strategy

    total_runs = sum(v.total_runs for v in variants)

    # Cold-start: if no runs exist, return the first untested variant
    if total_runs == 0:
        return variants[0].strategy

    best_score = -1.0
    best_strategy = variants[0].strategy

    for variant in variants:
        if variant.total_runs == 0:
            # Untested variants get infinite UCB1 score (explore first)
            return variant.strategy

        exploitation = variant.wins / variant.total_runs
        exploration = exploration_constant * math.sqrt(math.log(total_runs) / variant.total_runs)
        ucb1 = exploitation + exploration

        if ucb1 > best_score:
            best_score = ucb1
            best_strategy = variant.strategy

    return best_strategy


def round_robin_schedule(
    strategies: list[EvolutionaryStrategy],
    task_count: int,
) -> list[tuple[EvolutionaryStrategy, int]]:
    """Distribute tasks evenly across strategies for initial seeding.

    Returns a list of ``(strategy, assigned_task_count)`` pairs.

    Parameters
    ----------
    strategies:
        Strategies to distribute tasks across.
    task_count:
        Total number of tasks to assign.

    Raises
    ------
    ValueError
        If *strategies* is empty or *task_count* is negative.
    """
    if not strategies:
        msg = "strategies must not be empty"
        raise ValueError(msg)
    if task_count < 0:
        msg = "task_count must be non-negative"
        raise ValueError(msg)

    n = len(strategies)
    base, remainder = divmod(task_count, n)

    result: list[tuple[EvolutionaryStrategy, int]] = []
    for i, strategy in enumerate(strategies):
        count = base + (1 if i < remainder else 0)
        result.append((strategy, count))

    return result
