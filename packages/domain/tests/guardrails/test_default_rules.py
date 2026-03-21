"""Unit tests for the default guardrail rules."""

from __future__ import annotations

from lintel.domain.guardrails.default_rules import DEFAULT_RULES
from lintel.domain.guardrails.models import GuardrailAction, GuardrailRule


class TestDefaultRulesCollection:
    def test_is_tuple(self) -> None:
        assert isinstance(DEFAULT_RULES, tuple)

    def test_has_seven_rules(self) -> None:
        assert len(DEFAULT_RULES) == 7

    def test_all_are_guardrail_rules(self) -> None:
        for rule in DEFAULT_RULES:
            assert isinstance(rule, GuardrailRule)

    def test_unique_rule_ids(self) -> None:
        ids = [r.rule_id for r in DEFAULT_RULES]
        assert len(ids) == len(set(ids))

    def test_unique_names(self) -> None:
        names = [r.name for r in DEFAULT_RULES]
        assert len(names) == len(set(names))

    def test_all_is_default_true(self) -> None:
        for rule in DEFAULT_RULES:
            assert rule.is_default is True, f"{rule.name} should be is_default=True"

    def test_all_enabled(self) -> None:
        for rule in DEFAULT_RULES:
            assert rule.enabled is True, f"{rule.name} should be enabled=True"


class TestDefaultRulesStableUUIDs:
    """Ensure rule UUIDs are stable across releases."""

    EXPECTED_IDS = (
        "d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d51",
        "d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d52",
        "d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d53",
        "d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d54",
        "d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d55",
        "d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d56",
        "d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d57",
    )

    def test_rule_ids_match(self) -> None:
        actual_ids = tuple(r.rule_id for r in DEFAULT_RULES)
        assert actual_ids == self.EXPECTED_IDS


def _rule_by_name(name: str) -> GuardrailRule:
    for rule in DEFAULT_RULES:
        if rule.name == name:
            return rule
    raise ValueError(f"No default rule named {name!r}")


class TestAgentReworkWarning:
    def test_action(self) -> None:
        assert _rule_by_name("agent_rework_warning").action == GuardrailAction.WARN

    def test_event_type(self) -> None:
        assert _rule_by_name("agent_rework_warning").event_type == "RunCompleted"

    def test_threshold(self) -> None:
        assert _rule_by_name("agent_rework_warning").threshold == 0.2

    def test_cooldown(self) -> None:
        assert _rule_by_name("agent_rework_warning").cooldown_seconds == 300

    def test_condition(self) -> None:
        assert _rule_by_name("agent_rework_warning").condition == "rework_rate > threshold"


class TestCostWarning:
    def test_action(self) -> None:
        assert _rule_by_name("cost_warning").action == GuardrailAction.WARN

    def test_event_type(self) -> None:
        assert _rule_by_name("cost_warning").event_type == "RunCompleted"

    def test_threshold(self) -> None:
        assert _rule_by_name("cost_warning").threshold == 5.0

    def test_cooldown(self) -> None:
        assert _rule_by_name("cost_warning").cooldown_seconds == 600


class TestCostEscalation:
    def test_action(self) -> None:
        assert _rule_by_name("cost_escalation").action == GuardrailAction.REQUIRE_APPROVAL

    def test_event_type(self) -> None:
        assert _rule_by_name("cost_escalation").event_type == "PullRequestCreated"

    def test_threshold(self) -> None:
        assert _rule_by_name("cost_escalation").threshold == 100.0

    def test_cooldown(self) -> None:
        assert _rule_by_name("cost_escalation").cooldown_seconds == 3600


class TestSandboxTimeout:
    def test_action(self) -> None:
        assert _rule_by_name("sandbox_timeout").action == GuardrailAction.WARN

    def test_event_type(self) -> None:
        assert _rule_by_name("sandbox_timeout").event_type == "SandboxCommandFinished"

    def test_threshold(self) -> None:
        assert _rule_by_name("sandbox_timeout").threshold == 1800.0

    def test_cooldown(self) -> None:
        assert _rule_by_name("sandbox_timeout").cooldown_seconds == 60


class TestTestFailureBlock:
    def test_action(self) -> None:
        assert _rule_by_name("test_failure_block").action == GuardrailAction.BLOCK

    def test_event_type(self) -> None:
        assert _rule_by_name("test_failure_block").event_type == "TestResultRecorded"

    def test_threshold_is_none(self) -> None:
        assert _rule_by_name("test_failure_block").threshold is None

    def test_cooldown(self) -> None:
        assert _rule_by_name("test_failure_block").cooldown_seconds == 0


class TestLargeDiffReview:
    def test_action(self) -> None:
        assert _rule_by_name("large_diff_review").action == GuardrailAction.REQUIRE_APPROVAL

    def test_event_type(self) -> None:
        assert _rule_by_name("large_diff_review").event_type == "PullRequestCreated"

    def test_threshold(self) -> None:
        assert _rule_by_name("large_diff_review").threshold == 500.0

    def test_cooldown(self) -> None:
        assert _rule_by_name("large_diff_review").cooldown_seconds == 0


class TestPiiInArtifacts:
    def test_action(self) -> None:
        assert _rule_by_name("pii_in_artifacts").action == GuardrailAction.BLOCK

    def test_event_type(self) -> None:
        assert _rule_by_name("pii_in_artifacts").event_type == "ArtifactCreated"

    def test_threshold_is_none(self) -> None:
        assert _rule_by_name("pii_in_artifacts").threshold is None

    def test_cooldown(self) -> None:
        assert _rule_by_name("pii_in_artifacts").cooldown_seconds == 0


class TestThresholdPresence:
    """Rules with > threshold conditions must have non-None thresholds."""

    RULES_WITH_THRESHOLDS = (
        "agent_rework_warning",
        "cost_warning",
        "cost_escalation",
        "sandbox_timeout",
        "large_diff_review",
    )
    RULES_WITHOUT_THRESHOLDS = (
        "test_failure_block",
        "pii_in_artifacts",
    )

    def test_rules_with_thresholds_have_values(self) -> None:
        for name in self.RULES_WITH_THRESHOLDS:
            rule = _rule_by_name(name)
            assert rule.threshold is not None, f"{name} should have a threshold"

    def test_rules_without_thresholds_are_none(self) -> None:
        for name in self.RULES_WITHOUT_THRESHOLDS:
            rule = _rule_by_name(name)
            assert rule.threshold is None, f"{name} should have threshold=None"
