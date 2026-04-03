"""Tests for the anti-overfitting guard."""

from lintel.improvement_api.overfit_guard import (
    MIN_CLASS_RUNS,
    check_overfitting,
)


class TestOverfitGuard:
    def test_rejects_single_task_fix(self) -> None:
        result = check_overfitting(
            target_class="test_failure",
            class_pass_rate_before=0.5,
            class_pass_rate_after=1.0,
            affected_runs=1,
            overall_pass_rate_before=0.8,
            overall_pass_rate_after=0.85,
        )
        assert not result.passed
        assert "1 run" in result.reason

    def test_rejects_no_class_improvement(self) -> None:
        result = check_overfitting(
            target_class="sandbox",
            class_pass_rate_before=0.6,
            class_pass_rate_after=0.6,
            affected_runs=5,
            overall_pass_rate_before=0.8,
            overall_pass_rate_after=0.8,
        )
        assert not result.passed
        assert "did not improve" in result.reason

    def test_rejects_overall_regression(self) -> None:
        result = check_overfitting(
            target_class="timeout",
            class_pass_rate_before=0.3,
            class_pass_rate_after=0.9,
            affected_runs=5,
            overall_pass_rate_before=0.8,
            overall_pass_rate_after=0.6,
        )
        assert not result.passed
        assert "regressed" in result.reason

    def test_accepts_valid_improvement(self) -> None:
        result = check_overfitting(
            target_class="test_failure",
            class_pass_rate_before=0.4,
            class_pass_rate_after=0.8,
            affected_runs=10,
            overall_pass_rate_before=0.7,
            overall_pass_rate_after=0.85,
        )
        assert result.passed
        assert "improved" in result.reason
        assert result.target_class == "test_failure"
        assert result.affected_runs == 10

    def test_boundary_min_class_runs(self) -> None:
        result = check_overfitting(
            target_class="auth",
            class_pass_rate_before=0.0,
            class_pass_rate_after=1.0,
            affected_runs=MIN_CLASS_RUNS,
            overall_pass_rate_before=0.9,
            overall_pass_rate_after=0.95,
        )
        assert result.passed

    def test_marginal_improvement_accepted(self) -> None:
        result = check_overfitting(
            target_class="pr_creation",
            class_pass_rate_before=0.5,
            class_pass_rate_after=0.52,
            affected_runs=3,
            overall_pass_rate_before=0.8,
            overall_pass_rate_after=0.81,
        )
        assert result.passed
