"""Unit tests for the GuardrailEngine."""

from __future__ import annotations

from uuid import uuid4

import pytest

from lintel.contracts.events import EventEnvelope
from lintel.domain.guardrails.engine import GuardrailBlockError, GuardrailEngine
from lintel.domain.guardrails.models import GuardrailAction, GuardrailRule

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockRuleRepo:
    def __init__(self, rules: list[GuardrailRule] | None = None) -> None:
        self._rules: dict[str, GuardrailRule] = {}
        if rules:
            for r in rules:
                self._rules[r.rule_id] = r

    async def list_enabled(self) -> list[GuardrailRule]:
        return [r for r in self._rules.values() if r.enabled]

    async def list_by_event_type(self, event_type: str) -> list[GuardrailRule]:
        return [r for r in self._rules.values() if r.event_type == event_type and r.enabled]

    async def get(self, rule_id: str) -> GuardrailRule | None:
        return self._rules.get(rule_id)

    async def upsert(self, rule: GuardrailRule) -> None:
        self._rules[rule.rule_id] = rule

    async def delete(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None


class MockEventBus:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def publish(self, event: EventEnvelope) -> None:
        self.published.append(event)

    async def subscribe(self, event_types: frozenset[str], handler: object) -> str:
        return "mock-sub-id"

    async def unsubscribe(self, subscription_id: str) -> None:
        pass


def _make_event(event_type: str, payload: dict) -> EventEnvelope:  # type: ignore[type-arg]
    return EventEnvelope(
        event_type=event_type,
        payload=payload,
        correlation_id=uuid4(),
    )


# ---------------------------------------------------------------------------
# Rework rate (WARN)
# ---------------------------------------------------------------------------


class TestReworkRateWarning:
    RULE = GuardrailRule(
        rule_id="d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d51",
        name="agent_rework_warning",
        event_type="RunCompleted",
        condition="rework_rate > threshold",
        action=GuardrailAction.WARN,
        threshold=0.2,
    )

    async def test_triggers_when_above_threshold(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("RunCompleted", {"rework_rate": 0.3})
        await engine.handle(event)
        assert len(bus.published) == 1
        assert bus.published[0].payload["rule_name"] == "agent_rework_warning"
        assert bus.published[0].payload["action"] == "WARN"

    async def test_does_not_trigger_below_threshold(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("RunCompleted", {"rework_rate": 0.1})
        await engine.handle(event)
        assert len(bus.published) == 0


# ---------------------------------------------------------------------------
# Run cost (WARN)
# ---------------------------------------------------------------------------


class TestCostWarning:
    RULE = GuardrailRule(
        rule_id="d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d52",
        name="cost_warning",
        event_type="RunCompleted",
        condition="run_cost > threshold",
        action=GuardrailAction.WARN,
        threshold=5.0,
    )

    async def test_triggers_when_above_threshold(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("RunCompleted", {"run_cost": 10})
        await engine.handle(event)
        assert len(bus.published) == 1
        assert bus.published[0].payload["rule_name"] == "cost_warning"

    async def test_does_not_trigger_below_threshold(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("RunCompleted", {"run_cost": 3.0})
        await engine.handle(event)
        assert len(bus.published) == 0


# ---------------------------------------------------------------------------
# Test verdict (BLOCK)
# ---------------------------------------------------------------------------


class TestTestFailureBlock:
    RULE = GuardrailRule(
        rule_id="d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d55",
        name="test_failure_block",
        event_type="TestResultRecorded",
        condition="verdict == 'failed'",
        action=GuardrailAction.BLOCK,
    )

    async def test_blocks_on_failed_verdict(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("TestResultRecorded", {"verdict": "failed"})
        with pytest.raises(GuardrailBlockError) as exc_info:
            await engine.handle(event)
        assert exc_info.value.rule_id == self.RULE.rule_id
        assert exc_info.value.rule_name == "test_failure_block"
        # Event should still be published before the raise
        assert len(bus.published) == 1

    async def test_does_not_block_on_passed_verdict(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("TestResultRecorded", {"verdict": "passed"})
        await engine.handle(event)
        assert len(bus.published) == 0


# ---------------------------------------------------------------------------
# PII detection (BLOCK)
# ---------------------------------------------------------------------------


class TestPiiBlock:
    RULE = GuardrailRule(
        rule_id="d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d57",
        name="pii_in_artifacts",
        event_type="ArtifactCreated",
        condition="pii_detected == true",
        action=GuardrailAction.BLOCK,
    )

    async def test_blocks_when_pii_detected(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("ArtifactCreated", {"pii_detected": True})
        with pytest.raises(GuardrailBlockError) as exc_info:
            await engine.handle(event)
        assert exc_info.value.rule_name == "pii_in_artifacts"
        assert len(bus.published) == 1

    async def test_does_not_block_when_no_pii(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("ArtifactCreated", {"pii_detected": False})
        await engine.handle(event)
        assert len(bus.published) == 0


# ---------------------------------------------------------------------------
# Large diff review (REQUIRE_APPROVAL)
# ---------------------------------------------------------------------------


class TestLargeDiffReview:
    RULE = GuardrailRule(
        rule_id="d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d56",
        name="large_diff_review",
        event_type="PullRequestCreated",
        condition="lines_changed > threshold",
        action=GuardrailAction.REQUIRE_APPROVAL,
        threshold=500.0,
    )

    async def test_triggers_when_above_threshold(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("PullRequestCreated", {"lines_changed": 600})
        await engine.handle(event)
        assert len(bus.published) == 1
        assert bus.published[0].payload["action"] == "REQUIRE_APPROVAL"

    async def test_does_not_trigger_below_threshold(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("PullRequestCreated", {"lines_changed": 100})
        await engine.handle(event)
        assert len(bus.published) == 0


# ---------------------------------------------------------------------------
# Sandbox timeout (WARN)
# ---------------------------------------------------------------------------


class TestSandboxTimeout:
    RULE = GuardrailRule(
        rule_id="d47f4a01-1c3a-4b8e-9f6d-0e1a2b3c4d54",
        name="sandbox_timeout",
        event_type="SandboxCommandFinished",
        condition="duration_seconds > threshold",
        action=GuardrailAction.WARN,
        threshold=1800.0,
    )

    async def test_triggers_when_above_threshold(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("SandboxCommandFinished", {"duration_seconds": 2000})
        await engine.handle(event)
        assert len(bus.published) == 1
        assert bus.published[0].payload["rule_name"] == "sandbox_timeout"

    async def test_does_not_trigger_below_threshold(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([self.RULE]), event_bus=bus)
        event = _make_event("SandboxCommandFinished", {"duration_seconds": 100})
        await engine.handle(event)
        assert len(bus.published) == 0


# ---------------------------------------------------------------------------
# Disabled rules
# ---------------------------------------------------------------------------


class TestDisabledRulesSkipped:
    async def test_disabled_rule_does_not_trigger(self) -> None:
        disabled_rule = GuardrailRule(
            rule_id="disabled-1",
            name="disabled_rule",
            event_type="RunCompleted",
            condition="rework_rate > threshold",
            action=GuardrailAction.WARN,
            threshold=0.2,
            enabled=False,
        )
        bus = MockEventBus()
        # The MockRuleRepo.list_by_event_type already filters by enabled,
        # so the engine never sees it — matching real behaviour.
        engine = GuardrailEngine(MockRuleRepo([disabled_rule]), event_bus=bus)
        event = _make_event("RunCompleted", {"rework_rate": 0.9})
        await engine.handle(event)
        assert len(bus.published) == 0


# ---------------------------------------------------------------------------
# No event bus configured
# ---------------------------------------------------------------------------


class TestNoEventBus:
    async def test_warn_without_bus_does_not_error(self) -> None:
        rule = GuardrailRule(
            rule_id="r1",
            name="no_bus_warn",
            event_type="RunCompleted",
            condition="rework_rate > threshold",
            action=GuardrailAction.WARN,
            threshold=0.1,
        )
        engine = GuardrailEngine(MockRuleRepo([rule]), event_bus=None)
        event = _make_event("RunCompleted", {"rework_rate": 0.5})
        # Should not raise even without an event bus
        await engine.handle(event)

    async def test_block_without_bus_still_raises(self) -> None:
        rule = GuardrailRule(
            rule_id="r2",
            name="no_bus_block",
            event_type="TestResultRecorded",
            condition="verdict == 'failed'",
            action=GuardrailAction.BLOCK,
        )
        engine = GuardrailEngine(MockRuleRepo([rule]), event_bus=None)
        event = _make_event("TestResultRecorded", {"verdict": "failed"})
        with pytest.raises(GuardrailBlockError):
            await engine.handle(event)


# ---------------------------------------------------------------------------
# No matching rules
# ---------------------------------------------------------------------------


class TestNoMatchingRules:
    async def test_unmatched_event_type_is_noop(self) -> None:
        bus = MockEventBus()
        engine = GuardrailEngine(MockRuleRepo([]), event_bus=bus)
        event = _make_event("UnknownEvent", {"foo": "bar"})
        await engine.handle(event)
        assert len(bus.published) == 0


# ---------------------------------------------------------------------------
# GuardrailBlockError attributes
# ---------------------------------------------------------------------------


class TestGuardrailBlockError:
    def test_attributes(self) -> None:
        err = GuardrailBlockError(rule_id="abc", rule_name="my_rule")
        assert err.rule_id == "abc"
        assert err.rule_name == "my_rule"

    def test_default_message(self) -> None:
        err = GuardrailBlockError(rule_id="abc", rule_name="my_rule")
        assert "my_rule" in str(err)

    def test_custom_message(self) -> None:
        err = GuardrailBlockError(rule_id="abc", rule_name="my_rule", message="custom msg")
        assert str(err) == "custom msg"

    def test_is_exception(self) -> None:
        assert issubclass(GuardrailBlockError, Exception)
