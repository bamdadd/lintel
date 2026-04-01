"""Evolutionary strategy types (REQ-034.2.2/034.2.3).

Defines agent strategy configurations that can be mutated and
selected through tournament-style competition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class EvolutionaryStrategyStatus(StrEnum):
    """Lifecycle status of an evolutionary strategy."""

    ACTIVE = "active"
    PRUNED = "pruned"
    PROMOTED = "promoted"


@dataclass(frozen=True)
class EvolutionaryStrategy:
    """An agent strategy configuration subject to mutation and tournament selection.

    The ``config`` dict holds model, prompt template, tool subset, and timeout
    values.  ``parent_strategy_id`` tracks lineage so the full mutation
    history can be reconstructed as a tree.
    """

    strategy_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    parent_strategy_id: str = ""
    status: EvolutionaryStrategyStatus = EvolutionaryStrategyStatus.ACTIVE
    score: float | None = None
    generation: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class StrategyMutationProposal:
    """Output of the strategy mutation process.

    Contains the proposed new configuration, a human-readable rationale,
    and a reference to the parent strategy that was mutated.
    """

    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    parent_strategy_id: str = ""
    proposed_config: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    config_deltas: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FailedRunContext:
    """Context provided to the strategist agent when a run fails.

    Carries enough information for the agent to diagnose what went wrong
    and propose a strategy mutation.
    """

    run_id: str = ""
    strategy_id: str = ""
    failure_reason: str = ""
    metrics: tuple[dict[str, Any], ...] = ()
    current_config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MutationConfig:
    """Valid ranges and options for strategy mutations."""

    allowed_models: tuple[str, ...] = (
        "claude-sonnet-4-20250514",
        "claude-haiku-4-20250414",
        "gpt-4o",
        "gpt-4o-mini",
    )
    prompt_variants: tuple[str, ...] = ()
    tool_pool: tuple[str, ...] = ()
    timeout_range: tuple[int, int] = (30, 300)
    temperature_range: tuple[float, float] = (0.0, 1.0)
    max_retries_range: tuple[int, int] = (0, 5)


@dataclass(frozen=True)
class StrategyScore:
    """Win/loss record for a strategy in tournament selection."""

    strategy: EvolutionaryStrategy
    wins: int = 0
    total_runs: int = 0


@dataclass(frozen=True)
class TournamentResult:
    """Outcome of a tournament round."""

    winner: EvolutionaryStrategy
    pruned: tuple[EvolutionaryStrategy, ...] = ()
    scores: tuple[StrategyScore, ...] = ()
