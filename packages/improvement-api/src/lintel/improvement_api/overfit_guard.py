"""Anti-overfitting guard for the auto-improvement loop.

Ensures that improvement changes fix a CLASS of failures, not just
an individual task. A change is accepted only when the pass rate for
the targeted failure class improves across multiple runs.
"""

from __future__ import annotations

from lintel.improvement_api.types import OverfitCheck

# Minimum number of runs that must be affected for a class-level judgement.
MIN_CLASS_RUNS = 2

# The class pass rate must improve by at least this fraction.
MIN_CLASS_IMPROVEMENT = 0.01


def check_overfitting(
    *,
    target_class: str,
    class_pass_rate_before: float,
    class_pass_rate_after: float,
    affected_runs: int,
    overall_pass_rate_before: float,
    overall_pass_rate_after: float,
) -> OverfitCheck:
    """Validate that an improvement change is not overfitting.

    Returns an :class:`OverfitCheck` with ``passed=True`` only when:
    1. More than one run is affected (not a single-task fix).
    2. The failure class pass rate actually improved.
    3. The overall pass rate did not regress.
    """
    if affected_runs < MIN_CLASS_RUNS:
        return OverfitCheck(
            passed=False,
            reason=f"Only {affected_runs} run(s) affected — need >= {MIN_CLASS_RUNS}",
            target_class=target_class,
            class_pass_rate_before=class_pass_rate_before,
            class_pass_rate_after=class_pass_rate_after,
            affected_runs=affected_runs,
        )

    improvement = class_pass_rate_after - class_pass_rate_before
    if improvement < MIN_CLASS_IMPROVEMENT:
        return OverfitCheck(
            passed=False,
            reason=(
                f"Class '{target_class}' pass rate did not improve "
                f"({class_pass_rate_before:.2%} -> {class_pass_rate_after:.2%})"
            ),
            target_class=target_class,
            class_pass_rate_before=class_pass_rate_before,
            class_pass_rate_after=class_pass_rate_after,
            affected_runs=affected_runs,
        )

    if overall_pass_rate_after < overall_pass_rate_before - MIN_CLASS_IMPROVEMENT:
        return OverfitCheck(
            passed=False,
            reason=(
                f"Overall pass rate regressed "
                f"({overall_pass_rate_before:.2%} -> {overall_pass_rate_after:.2%})"
            ),
            target_class=target_class,
            class_pass_rate_before=class_pass_rate_before,
            class_pass_rate_after=class_pass_rate_after,
            affected_runs=affected_runs,
        )

    return OverfitCheck(
        passed=True,
        reason=f"Class '{target_class}' improved by {improvement:.2%}",
        target_class=target_class,
        class_pass_rate_before=class_pass_rate_before,
        class_pass_rate_after=class_pass_rate_after,
        affected_runs=affected_runs,
    )
