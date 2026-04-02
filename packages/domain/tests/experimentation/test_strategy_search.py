"""Tests for parallel strategy search engine."""

from __future__ import annotations

import pytest

from lintel.domain.experimentation.strategy_search import (
    OptimizationDirection,
    SearchGoal,
    StrategySearchEngine,
    StrategyVariant,
    VariantResult,
)


@pytest.fixture
def engine() -> StrategySearchEngine:
    return StrategySearchEngine(seed=42)


@pytest.fixture
def base_config() -> dict[str, object]:
    return {"learning_rate": 0.01, "batch_size": 32, "model": "gpt-4"}


@pytest.fixture
def maximize_goal() -> SearchGoal:
    return SearchGoal(metric_name="accuracy", direction=OptimizationDirection.MAXIMIZE)


@pytest.fixture
def minimize_goal() -> SearchGoal:
    return SearchGoal(
        metric_name="latency",
        direction=OptimizationDirection.MINIMIZE,
        target_value=100.0,
    )


# --- StrategyVariant ---


def test_strategy_variant_is_frozen() -> None:
    v = StrategyVariant(id="a", name="test", config={"x": 1})
    with pytest.raises(AttributeError):
        v.id = "b"  # type: ignore[misc]


def test_strategy_variant_defaults() -> None:
    v = StrategyVariant(id="a", name="test", config={})
    assert v.parent_id is None
    assert v.generation == 0


# --- SearchGoal ---


def test_search_goal_is_frozen() -> None:
    g = SearchGoal(metric_name="acc", direction=OptimizationDirection.MAXIMIZE)
    with pytest.raises(AttributeError):
        g.metric_name = "x"  # type: ignore[misc]


def test_search_goal_target_value_optional() -> None:
    g = SearchGoal(metric_name="acc", direction=OptimizationDirection.MAXIMIZE)
    assert g.target_value is None


# --- VariantResult ---


def test_variant_result_is_frozen() -> None:
    r = VariantResult(
        variant_id="a", run_id="r1", metric_values={}, duration_seconds=1.0, success=True
    )
    with pytest.raises(AttributeError):
        r.success = False  # type: ignore[misc]


# --- generate_variants ---


def test_generate_variants_count(
    engine: StrategySearchEngine, base_config: dict[str, object]
) -> None:
    variants = engine.generate_variants(base_config, 5)
    assert len(variants) == 5


def test_generate_variants_unique_ids(
    engine: StrategySearchEngine, base_config: dict[str, object]
) -> None:
    variants = engine.generate_variants(base_config, 5)
    ids = [v.id for v in variants]
    assert len(set(ids)) == 5


def test_generate_variants_preserves_non_numeric(
    engine: StrategySearchEngine, base_config: dict[str, object]
) -> None:
    variants = engine.generate_variants(base_config, 10)
    for v in variants:
        assert v.config["model"] == "gpt-4"


def test_generate_variants_generation(
    engine: StrategySearchEngine, base_config: dict[str, object]
) -> None:
    variants = engine.generate_variants(base_config, 3, generation=2)
    for v in variants:
        assert v.generation == 2


def test_generate_variants_parent_id(
    engine: StrategySearchEngine, base_config: dict[str, object]
) -> None:
    variants = engine.generate_variants(base_config, 2, parent_id="parent-1")
    for v in variants:
        assert v.parent_id == "parent-1"


def test_generate_variants_invalid_count(
    engine: StrategySearchEngine, base_config: dict[str, object]
) -> None:
    with pytest.raises(ValueError, match="num_variants"):
        engine.generate_variants(base_config, 0)


# --- evaluate_results ---


def test_evaluate_results_maximize(engine: StrategySearchEngine, maximize_goal: SearchGoal) -> None:
    results = [
        VariantResult(
            variant_id="a",
            run_id="r1",
            metric_values={"accuracy": 0.8},
            duration_seconds=1.0,
            success=True,
        ),
        VariantResult(
            variant_id="b",
            run_id="r2",
            metric_values={"accuracy": 0.95},
            duration_seconds=1.0,
            success=True,
        ),
        VariantResult(
            variant_id="c",
            run_id="r3",
            metric_values={"accuracy": 0.7},
            duration_seconds=1.0,
            success=True,
        ),
    ]
    ranked = engine.evaluate_results(results, maximize_goal)
    assert [r.variant_id for r in ranked] == ["b", "a", "c"]


def test_evaluate_results_minimize(engine: StrategySearchEngine, minimize_goal: SearchGoal) -> None:
    results = [
        VariantResult(
            variant_id="a",
            run_id="r1",
            metric_values={"latency": 200.0},
            duration_seconds=1.0,
            success=True,
        ),
        VariantResult(
            variant_id="b",
            run_id="r2",
            metric_values={"latency": 50.0},
            duration_seconds=1.0,
            success=True,
        ),
        VariantResult(
            variant_id="c",
            run_id="r3",
            metric_values={"latency": 150.0},
            duration_seconds=1.0,
            success=True,
        ),
    ]
    ranked = engine.evaluate_results(results, minimize_goal)
    assert [r.variant_id for r in ranked] == ["b", "c", "a"]


def test_evaluate_results_failed_last(
    engine: StrategySearchEngine, maximize_goal: SearchGoal
) -> None:
    results = [
        VariantResult(
            variant_id="a",
            run_id="r1",
            metric_values={"accuracy": 0.5},
            duration_seconds=1.0,
            success=True,
        ),
        VariantResult(
            variant_id="b",
            run_id="r2",
            metric_values={"accuracy": 0.99},
            duration_seconds=1.0,
            success=False,
        ),
    ]
    ranked = engine.evaluate_results(results, maximize_goal)
    assert ranked[0].variant_id == "a"
    assert ranked[1].variant_id == "b"


# --- select_winners ---


def test_select_winners_top_k(engine: StrategySearchEngine, maximize_goal: SearchGoal) -> None:
    results = [
        VariantResult(
            variant_id="a",
            run_id="r1",
            metric_values={"accuracy": 0.8},
            duration_seconds=1.0,
            success=True,
        ),
        VariantResult(
            variant_id="b",
            run_id="r2",
            metric_values={"accuracy": 0.95},
            duration_seconds=1.0,
            success=True,
        ),
        VariantResult(
            variant_id="c",
            run_id="r3",
            metric_values={"accuracy": 0.7},
            duration_seconds=1.0,
            success=True,
        ),
    ]
    winners = engine.select_winners(results, maximize_goal, top_k=2)
    assert len(winners) == 2
    assert winners[0].variant_id == "b"
    assert winners[1].variant_id == "a"


def test_select_winners_invalid_top_k(
    engine: StrategySearchEngine, maximize_goal: SearchGoal
) -> None:
    with pytest.raises(ValueError, match="top_k"):
        engine.select_winners([], maximize_goal, top_k=0)


# --- evolve ---


def test_evolve_produces_children(engine: StrategySearchEngine) -> None:
    winners = [
        StrategyVariant(id="w1", name="winner1", config={"lr": 0.01, "size": 32}),
        StrategyVariant(id="w2", name="winner2", config={"lr": 0.02, "size": 64}),
    ]
    children = engine.evolve(winners, generation=1, variants_per_winner=3)
    assert len(children) == 6


def test_evolve_sets_parent_id(engine: StrategySearchEngine) -> None:
    winners = [StrategyVariant(id="w1", name="winner1", config={"lr": 0.01})]
    children = engine.evolve(winners, generation=1, variants_per_winner=2)
    for child in children:
        assert child.parent_id == "w1"


def test_evolve_sets_generation(engine: StrategySearchEngine) -> None:
    winners = [StrategyVariant(id="w1", name="winner1", config={"lr": 0.01})]
    children = engine.evolve(winners, generation=3)
    for child in children:
        assert child.generation == 3


def test_evolve_empty_winners_raises(engine: StrategySearchEngine) -> None:
    with pytest.raises(ValueError, match="winners"):
        engine.evolve([], generation=1)


# --- meets_target ---


def test_meets_target_maximize(engine: StrategySearchEngine) -> None:
    goal = SearchGoal(
        metric_name="accuracy",
        direction=OptimizationDirection.MAXIMIZE,
        target_value=0.9,
    )
    good = VariantResult(
        variant_id="a",
        run_id="r1",
        metric_values={"accuracy": 0.95},
        duration_seconds=1.0,
        success=True,
    )
    bad = VariantResult(
        variant_id="b",
        run_id="r2",
        metric_values={"accuracy": 0.8},
        duration_seconds=1.0,
        success=True,
    )
    assert engine.meets_target(good, goal)
    assert not engine.meets_target(bad, goal)


def test_meets_target_minimize(engine: StrategySearchEngine) -> None:
    goal = SearchGoal(
        metric_name="latency",
        direction=OptimizationDirection.MINIMIZE,
        target_value=100.0,
    )
    good = VariantResult(
        variant_id="a",
        run_id="r1",
        metric_values={"latency": 50.0},
        duration_seconds=1.0,
        success=True,
    )
    bad = VariantResult(
        variant_id="b",
        run_id="r2",
        metric_values={"latency": 200.0},
        duration_seconds=1.0,
        success=True,
    )
    assert engine.meets_target(good, goal)
    assert not engine.meets_target(bad, goal)


def test_meets_target_no_target(engine: StrategySearchEngine) -> None:
    goal = SearchGoal(metric_name="accuracy", direction=OptimizationDirection.MAXIMIZE)
    r = VariantResult(
        variant_id="a",
        run_id="r1",
        metric_values={"accuracy": 0.99},
        duration_seconds=1.0,
        success=True,
    )
    assert not engine.meets_target(r, goal)


def test_meets_target_missing_metric(engine: StrategySearchEngine) -> None:
    goal = SearchGoal(
        metric_name="accuracy",
        direction=OptimizationDirection.MAXIMIZE,
        target_value=0.9,
    )
    r = VariantResult(
        variant_id="a",
        run_id="r1",
        metric_values={"latency": 50.0},
        duration_seconds=1.0,
        success=True,
    )
    assert not engine.meets_target(r, goal)


# --- mutation determinism ---


def test_deterministic_with_seed(base_config: dict[str, object]) -> None:
    e1 = StrategySearchEngine(seed=123)
    e2 = StrategySearchEngine(seed=123)
    v1 = e1.generate_variants(base_config, 5)
    v2 = e2.generate_variants(base_config, 5)
    for a, b in zip(v1, v2, strict=True):
        assert a.config == b.config


# --- end-to-end multi-generation ---


def test_multi_generation_search(base_config: dict[str, object]) -> None:
    engine = StrategySearchEngine(seed=7)
    goal = SearchGoal(
        metric_name="score",
        direction=OptimizationDirection.MAXIMIZE,
        target_value=100.0,
    )

    # Gen 0
    variants = engine.generate_variants(base_config, 4, generation=0)
    assert len(variants) == 4

    # Simulate results
    results = [
        VariantResult(
            variant_id=v.id,
            run_id=f"run-{v.id}",
            metric_values={"score": float(i * 10)},
            duration_seconds=1.0,
            success=True,
        )
        for i, v in enumerate(variants)
    ]

    # Select top 2
    winners_results = engine.select_winners(results, goal, top_k=2)
    assert len(winners_results) == 2

    # Map back to variants for evolve
    winner_map = {v.id: v for v in variants}
    winner_variants = [winner_map[r.variant_id] for r in winners_results]

    # Gen 1
    gen1 = engine.evolve(winner_variants, generation=1, variants_per_winner=2)
    assert len(gen1) == 4
    for child in gen1:
        assert child.generation == 1
        assert child.parent_id is not None
