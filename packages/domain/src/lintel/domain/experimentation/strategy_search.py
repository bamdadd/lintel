"""Parallel strategy search: goal-driven variant discovery.

Generates config mutations, evaluates results against a goal metric,
selects top-k winners, and evolves the next generation from winners.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import random


class OptimizationDirection(StrEnum):
    """Whether the goal metric should be maximized or minimized."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass(frozen=True)
class StrategyVariant:
    """A single strategy configuration variant."""

    id: str
    name: str
    config: dict[str, object]
    parent_id: str | None = None
    generation: int = 0


@dataclass(frozen=True)
class SearchGoal:
    """Defines the optimization objective for strategy search."""

    metric_name: str
    direction: OptimizationDirection
    target_value: float | None = None


@dataclass(frozen=True)
class VariantResult:
    """Outcome of evaluating a single variant."""

    variant_id: str
    run_id: str
    metric_values: dict[str, float]
    duration_seconds: float
    success: bool


def _variant_id(name: str, generation: int, index: int) -> str:
    """Generate a deterministic variant ID."""
    raw = f"{name}:gen{generation}:idx{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class StrategySearchEngine:
    """Manages parallel strategy search with evolutionary selection.

    Generates config mutations from a base config, ranks variant results
    against a SearchGoal, selects winners, and produces next-generation
    variants from the winners.
    """

    mutation_rate: float = 0.3
    seed: int | None = None
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    # -- public API --

    def generate_variants(
        self,
        base_config: dict[str, object],
        num_variants: int,
        *,
        generation: int = 0,
        parent_id: str | None = None,
    ) -> list[StrategyVariant]:
        """Create *num_variants* mutated copies of *base_config*."""
        if num_variants < 1:
            msg = "num_variants must be >= 1"
            raise ValueError(msg)
        variants: list[StrategyVariant] = []
        for i in range(num_variants):
            vid = _variant_id("variant", generation, i)
            mutated = self._mutate(base_config)
            variants.append(
                StrategyVariant(
                    id=vid,
                    name=f"variant-gen{generation}-{i}",
                    config=mutated,
                    parent_id=parent_id,
                    generation=generation,
                )
            )
        return variants

    def evaluate_results(
        self,
        results: list[VariantResult],
        goal: SearchGoal,
    ) -> list[VariantResult]:
        """Rank results best-first according to *goal*.

        Failed results are sorted to the end regardless of metric value.
        """

        def sort_key(r: VariantResult) -> tuple[int, float]:
            if not r.success:
                return (1, 0.0)
            val = r.metric_values.get(goal.metric_name, float("inf"))
            if goal.direction == OptimizationDirection.MAXIMIZE:
                return (0, -val)
            return (0, val)

        return sorted(results, key=sort_key)

    def select_winners(
        self,
        results: list[VariantResult],
        goal: SearchGoal,
        top_k: int = 1,
    ) -> list[VariantResult]:
        """Return the top-k results ranked by *goal*."""
        if top_k < 1:
            msg = "top_k must be >= 1"
            raise ValueError(msg)
        ranked = self.evaluate_results(results, goal)
        return ranked[:top_k]

    def evolve(
        self,
        winners: list[StrategyVariant],
        generation: int,
        *,
        variants_per_winner: int = 2,
    ) -> list[StrategyVariant]:
        """Create next-generation variants from *winners*.

        Each winner produces *variants_per_winner* mutated children.
        """
        if not winners:
            msg = "winners must not be empty"
            raise ValueError(msg)
        children: list[StrategyVariant] = []
        idx = 0
        for winner in winners:
            for _ in range(variants_per_winner):
                vid = _variant_id("evolved", generation, idx)
                mutated = self._mutate(winner.config)
                children.append(
                    StrategyVariant(
                        id=vid,
                        name=f"variant-gen{generation}-{idx}",
                        config=mutated,
                        parent_id=winner.id,
                        generation=generation,
                    )
                )
                idx += 1
        return children

    def meets_target(self, result: VariantResult, goal: SearchGoal) -> bool:
        """Check whether a result meets the goal's target_value."""
        if goal.target_value is None:
            return False
        val = result.metric_values.get(goal.metric_name)
        if val is None:
            return False
        if goal.direction == OptimizationDirection.MAXIMIZE:
            return val >= goal.target_value
        return val <= goal.target_value

    # -- internal --

    def _mutate(self, config: dict[str, object]) -> dict[str, object]:
        """Apply random mutations to numeric values in config."""
        result: dict[str, object] = {}
        for key, value in config.items():
            if isinstance(value, int | float) and self._rng.random() < self.mutation_rate:
                factor = 1.0 + self._rng.uniform(-0.5, 0.5)
                if isinstance(value, int):
                    result[key] = max(1, int(value * factor))
                else:
                    result[key] = value * factor
            else:
                result[key] = value
        return result
