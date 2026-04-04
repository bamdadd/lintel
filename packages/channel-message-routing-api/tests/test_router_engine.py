"""Tests for ChannelRouter engine."""

from __future__ import annotations

from lintel.channel_message_routing_api.router_engine import ChannelRouter
from lintel.channel_message_routing_api.store import RoutingRule


def _rule(**kwargs: object) -> RoutingRule:
    defaults = {
        "connection_id": "conn-1",
        "workflow_definition_id": "wf-1",
        "enabled": True,
        "priority": 0,
    }
    return RoutingRule(**{**defaults, **kwargs})  # type: ignore[arg-type]


class TestChannelRouter:
    def setup_method(self) -> None:
        self.router = ChannelRouter()

    def test_no_rules_returns_none(self) -> None:
        result = self.router.resolve([], "conn-1", "#general", "hello")
        assert result is None

    def test_matching_rule_returned(self) -> None:
        rule = _rule()
        result = self.router.resolve([rule], "conn-1", "#general", "hello")
        assert result is rule

    def test_higher_priority_wins(self) -> None:
        low = _rule(priority=1, workflow_definition_id="low")
        high = _rule(priority=10, workflow_definition_id="high")
        result = self.router.resolve([low, high], "conn-1", "#general", "hello")
        assert result is high

    def test_disabled_rules_skipped(self) -> None:
        rule = _rule(enabled=False)
        result = self.router.resolve([rule], "conn-1", "#general", "hello")
        assert result is None

    def test_channel_pattern_matching(self) -> None:
        rule = _rule(channel_pattern="#deploy-*")
        assert self.router.resolve([rule], "conn-1", "#deploy-prod", "go") is rule
        assert self.router.resolve([rule], "conn-1", "#general", "go") is None

    def test_message_pattern_matching(self) -> None:
        rule = _rule(message_pattern="deploy")
        assert self.router.resolve([rule], "conn-1", "#general", "please deploy") is rule
        assert self.router.resolve([rule], "conn-1", "#general", "hello") is None

    def test_wrong_connection_id_no_match(self) -> None:
        rule = _rule(connection_id="conn-1")
        result = self.router.resolve([rule], "conn-2", "#general", "hello")
        assert result is None
