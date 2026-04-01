"""Strategist agent role (REQ-034.2).

Wraps LLM calls to generate human-readable mutation rationale and
suggested config deltas, then merges LLM output with domain-layer
mutation logic.  Also orchestrates tournament execution.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.evolutionary_strategy import (
    EvolutionaryStrategy,
    FailedRunContext,
    StrategyMutationProposal,
    StrategyScore,
    TournamentResult,
)
from lintel.domain.strategy_mutation import mutate_strategy
from lintel.domain.tournament_selection import select_variant


class StrategistAgent:
    """Agent responsible for strategy mutations and tournament orchestration.

    The agent combines LLM-generated insights (rationale, direction)
    with deterministic domain-layer mutation logic (valid ranges,
    config constraints).
    """

    def __init__(
        self,
        *,
        model_router: Any = None,  # noqa: ANN401
        event_store: Any = None,  # noqa: ANN401
        event_bus: Any = None,  # noqa: ANN401
        strategy_store: Any = None,  # noqa: ANN401
    ) -> None:
        self._model_router = model_router
        self._event_store = event_store
        self._event_bus = event_bus
        self._strategy_store = strategy_store

    async def execute(
        self,
        context: FailedRunContext,
    ) -> StrategyMutationProposal:
        """Generate a strategy mutation proposal for a failed run.

        1. Build a prompt from FailedRunContext
        2. Call LLM for rationale + suggested direction (if router available)
        3. Apply domain-layer mutation logic
        4. Return the merged proposal
        """
        # Reconstruct the strategy from the store if available
        strategy: EvolutionaryStrategy | None = None
        if self._strategy_store and context.strategy_id:
            item = await self._strategy_store.get(context.strategy_id)
            if item is not None:
                data = item if isinstance(item, dict) else asdict(item)
                strategy = EvolutionaryStrategy(
                    strategy_id=data.get("strategy_id", context.strategy_id),
                    name=data.get("name", ""),
                    config=data.get("config", {}),
                    parent_strategy_id=data.get("parent_strategy_id", ""),
                    generation=data.get("generation", 0),
                )

        if strategy is None:
            strategy = EvolutionaryStrategy(
                strategy_id=context.strategy_id,
                config=context.current_config,
            )

        # Generate domain-level mutation
        proposal = mutate_strategy(strategy, context)

        # If an LLM router is available, enhance the rationale
        if self._model_router is not None:
            llm_rationale = await self._generate_llm_rationale(context, proposal)
            if llm_rationale:
                proposal = StrategyMutationProposal(
                    proposal_id=proposal.proposal_id,
                    parent_strategy_id=proposal.parent_strategy_id,
                    proposed_config=proposal.proposed_config,
                    rationale=llm_rationale,
                    config_deltas=proposal.config_deltas,
                )

        return proposal

    async def _generate_llm_rationale(
        self,
        context: FailedRunContext,
        proposal: StrategyMutationProposal,
    ) -> str:
        """Call the LLM to produce a human-readable mutation rationale."""
        prompt = (
            "You are a strategy advisor for an AI agent orchestration system.\n"
            f"A run failed with reason: {context.failure_reason}\n"
            f"Current config: {context.current_config}\n"
            f"Proposed changes: {proposal.config_deltas}\n\n"
            "Provide a concise rationale (1-3 sentences) for why these "
            "changes should improve the next run."
        )
        try:
            result = await self._model_router.call_model(
                policy=None,
                messages=[{"role": "user", "content": prompt}],
                tools=None,
            )
            content = result.get("content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
        except Exception:
            pass
        return ""

    async def run_tournament(
        self,
        task_id: str,
        strategy_ids: list[str],
        scores: dict[str, StrategyScore],
    ) -> TournamentResult:
        """Execute a tournament round: select winner, promote/prune.

        Parameters
        ----------
        task_id:
            Identifier for the task being competed on.
        strategy_ids:
            IDs of strategies participating in the tournament.
        scores:
            Current win/loss records keyed by strategy_id.

        Returns
        -------
        TournamentResult with winner, pruned list, and final scores.
        """
        variants: list[StrategyScore] = []
        strategies: dict[str, EvolutionaryStrategy] = {}

        for sid in strategy_ids:
            score = scores.get(
                sid,
                StrategyScore(
                    strategy=EvolutionaryStrategy(strategy_id=sid),
                ),
            )
            variants.append(score)
            strategies[sid] = score.strategy

        winner = select_variant(variants)

        # Determine pruned strategies (those with 0 wins and enough runs)
        pruned: list[EvolutionaryStrategy] = []
        for variant in variants:
            if variant.strategy.strategy_id == winner.strategy_id:
                continue
            if variant.total_runs >= 3 and variant.wins == 0:
                pruned.append(variant.strategy)

        # Publish events if event bus is available
        if self._event_bus is not None:
            from lintel.domain.events import StrategyPromoted, StrategyPruned

            await self._event_bus.publish(
                StrategyPromoted(
                    payload={
                        "strategy_id": winner.strategy_id,
                        "tournament_id": task_id,
                        "score": winner.score if winner.score is not None else 0.0,
                        "competing_strategy_ids": strategy_ids,
                    },
                ),
            )
            for p in pruned:
                await self._event_bus.publish(
                    StrategyPruned(
                        payload={
                            "strategy_id": p.strategy_id,
                            "tournament_id": task_id,
                            "reason": "low_score",
                        },
                    ),
                )

        return TournamentResult(
            winner=winner,
            pruned=tuple(pruned),
            scores=tuple(variants),
        )
