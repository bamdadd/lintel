"""Strategy mutation logic (REQ-034.2.2).

Pure-function module that produces permuted config variants from an
existing strategy configuration.  No LLM dependency — the LLM-backed
rationale generation lives in the strategist agent.
"""

from __future__ import annotations

from dataclasses import replace
import random
from typing import Any

from lintel.domain.evolutionary_strategy import (
    EvolutionaryStrategy,
    FailedRunContext,
    MutationConfig,
    StrategyMutationProposal,
)

_DEFAULT_MUTATION_CONFIG = MutationConfig()


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _mutate_model(
    current: str,
    cfg: MutationConfig,
    rng: random.Random,
) -> str:
    """Pick a different model from the allowed pool."""
    candidates = [m for m in cfg.allowed_models if m != current]
    if not candidates:
        return current
    return rng.choice(candidates)


def _mutate_timeout(
    current: int,
    cfg: MutationConfig,
    rng: random.Random,
) -> int:
    """Randomly adjust timeout within allowed range."""
    lo, hi = cfg.timeout_range
    delta = rng.randint(-30, 30)
    return int(_clamp(current + delta, lo, hi))


def _mutate_temperature(
    current: float,
    cfg: MutationConfig,
    rng: random.Random,
) -> float:
    """Randomly adjust temperature within allowed range."""
    lo, hi = cfg.temperature_range
    delta = rng.uniform(-0.2, 0.2)
    return round(_clamp(current + delta, lo, hi), 2)


def _mutate_tools(
    current: list[str],
    cfg: MutationConfig,
    rng: random.Random,
) -> list[str]:
    """Add or remove a random tool from the pool."""
    pool = list(cfg.tool_pool)
    if not pool:
        return current
    current_set = set(current)
    available = [t for t in pool if t not in current_set]
    if available and (not current or rng.random() > 0.5):
        # Add a tool
        return sorted([*current, rng.choice(available)])
    if current:
        # Remove a random tool
        idx = rng.randrange(len(current))
        return current[:idx] + current[idx + 1 :]
    return current


def _mutate_max_retries(
    current: int,
    cfg: MutationConfig,
    rng: random.Random,
) -> int:
    lo, hi = cfg.max_retries_range
    delta = rng.choice([-1, 0, 1])
    return int(_clamp(current + delta, lo, hi))


def mutate_strategy(
    strategy: EvolutionaryStrategy,
    failed_run_context: FailedRunContext,
    mutation_config: MutationConfig | None = None,
    *,
    seed: int | None = None,
) -> StrategyMutationProposal:
    """Produce a mutated config variant from the given strategy.

    This is a pure function — deterministic when *seed* is provided.
    The mutation selects 1-3 config dimensions to vary.
    """
    cfg = mutation_config or _DEFAULT_MUTATION_CONFIG
    rng = random.Random(seed)

    current: dict[str, Any] = dict(strategy.config)
    proposed: dict[str, Any] = dict(current)
    deltas: dict[str, Any] = {}

    # Decide which dimensions to mutate (1-3)
    dimensions = ["model", "timeout", "temperature", "tools", "max_retries"]
    n_mutations = rng.randint(1, min(3, len(dimensions)))
    chosen = rng.sample(dimensions, n_mutations)

    for dim in chosen:
        if dim == "model":
            old_val = current.get("model", "")
            new_val = _mutate_model(str(old_val), cfg, rng)
            proposed["model"] = new_val
            deltas["model"] = {"old": old_val, "new": new_val}

        elif dim == "timeout":
            old_val = int(current.get("timeout", 120))
            new_val = _mutate_timeout(old_val, cfg, rng)
            proposed["timeout"] = new_val
            deltas["timeout"] = {"old": old_val, "new": new_val}

        elif dim == "temperature":
            old_val = float(current.get("temperature", 0.7))
            new_val = _mutate_temperature(old_val, cfg, rng)
            proposed["temperature"] = new_val
            deltas["temperature"] = {"old": old_val, "new": new_val}

        elif dim == "tools":
            old_val = list(current.get("tools", []))
            new_val = _mutate_tools(old_val, cfg, rng)
            proposed["tools"] = new_val
            deltas["tools"] = {"old": old_val, "new": new_val}

        elif dim == "max_retries":
            old_val = int(current.get("max_retries", 2))
            new_val = _mutate_max_retries(old_val, cfg, rng)
            proposed["max_retries"] = new_val
            deltas["max_retries"] = {"old": old_val, "new": new_val}

    rationale_parts = [f"Mutated {dim}" for dim in chosen]
    if failed_run_context.failure_reason:
        rationale_parts.append(f"in response to failure: {failed_run_context.failure_reason}")

    return StrategyMutationProposal(
        parent_strategy_id=strategy.strategy_id,
        proposed_config=proposed,
        rationale="; ".join(rationale_parts),
        config_deltas=deltas,
    )


def apply_mutation(
    parent: EvolutionaryStrategy,
    proposal: StrategyMutationProposal,
) -> EvolutionaryStrategy:
    """Create a new ``EvolutionaryStrategy`` from a parent + mutation proposal."""
    return replace(
        parent,
        strategy_id="",  # caller should assign a new ID
        name=f"{parent.name}_gen{parent.generation + 1}",
        config=dict(proposal.proposed_config),
        parent_strategy_id=parent.strategy_id,
        score=None,
        generation=parent.generation + 1,
    )
