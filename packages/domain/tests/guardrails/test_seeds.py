"""Unit tests for seed_default_guardrails."""

from __future__ import annotations

from lintel.domain.guardrails.default_rules import DEFAULT_RULES
from lintel.domain.guardrails.models import GuardrailRule
from lintel.domain.guardrails.seeds import seed_default_guardrails


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


class TestSeedDefaultGuardrails:
    async def test_inserts_all_seven_rules_on_first_call(self) -> None:
        repo = MockRuleRepo()
        await seed_default_guardrails(repo)
        stored = await repo.list_enabled()
        assert len(stored) == 7
        stored_ids = {r.rule_id for r in stored}
        expected_ids = {r.rule_id for r in DEFAULT_RULES}
        assert stored_ids == expected_ids

    async def test_idempotent_second_call(self) -> None:
        repo = MockRuleRepo()
        await seed_default_guardrails(repo)
        # Capture state after first seed
        first_pass = await repo.list_enabled()
        assert len(first_pass) == 7

        # Second call should not modify anything
        await seed_default_guardrails(repo)
        second_pass = await repo.list_enabled()
        assert len(second_pass) == 7

    async def test_preserves_existing_customised_rules(self) -> None:
        """If a rule already exists (e.g. team customisation), it is not overwritten."""
        # Pre-insert the first default rule with a modified threshold
        original = DEFAULT_RULES[0]
        customised = GuardrailRule(
            rule_id=original.rule_id,
            name=original.name,
            event_type=original.event_type,
            condition=original.condition,
            action=original.action,
            threshold=0.99,  # custom value
            cooldown_seconds=original.cooldown_seconds,
            is_default=original.is_default,
            enabled=original.enabled,
        )
        repo = MockRuleRepo([customised])

        await seed_default_guardrails(repo)

        # The customised rule should be preserved
        stored = await repo.get(original.rule_id)
        assert stored is not None
        assert stored.threshold == 0.99

        # All 7 rules should exist
        all_rules = await repo.list_enabled()
        assert len(all_rules) == 7

    async def test_each_inserted_rule_matches_default(self) -> None:
        repo = MockRuleRepo()
        await seed_default_guardrails(repo)
        for expected in DEFAULT_RULES:
            actual = await repo.get(expected.rule_id)
            assert actual == expected
