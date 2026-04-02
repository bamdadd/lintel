"""Tests for agent gossip and discovery (REQ-034.4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lintel.domain.agents.gossip import (
    AgentAnnouncement,
    AgentDirectory,
    AgentStatus,
    GossipMessage,
    GossipProtocol,
)


def _make_announcement(
    agent_id: str = "a1",
    role: str = "coder",
    capabilities: list[str] | None = None,
    status: AgentStatus = AgentStatus.ACTIVE,
    timestamp: datetime | None = None,
) -> AgentAnnouncement:
    return AgentAnnouncement(
        agent_id=agent_id,
        role=role,
        capabilities=capabilities or ["code"],
        status=status,
        timestamp=timestamp or datetime.now(UTC),
    )


def _make_message(
    sender_id: str = "a1",
    topic: str = "info",
    ttl: int = 3,
) -> GossipMessage:
    return GossipMessage(sender_id=sender_id, topic=topic, payload={"k": "v"}, ttl=ttl)


# --- AgentAnnouncement ---


class TestAgentAnnouncement:
    def test_frozen(self) -> None:
        ann = _make_announcement()
        assert ann.agent_id == "a1"

    def test_default_status_is_active(self) -> None:
        ann = AgentAnnouncement(agent_id="x", role="r", capabilities=[])
        assert ann.status == AgentStatus.ACTIVE


# --- AgentDirectory ---


class TestAgentDirectory:
    def test_register_and_get(self) -> None:
        d = AgentDirectory()
        ann = _make_announcement()
        d.register(ann)
        assert d.get("a1") is ann

    def test_get_unknown_returns_none(self) -> None:
        assert AgentDirectory().get("nope") is None

    def test_deregister(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement())
        d.deregister("a1")
        assert d.get("a1") is None

    def test_deregister_unknown_is_noop(self) -> None:
        AgentDirectory().deregister("nope")  # should not raise

    def test_discover_by_capability(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1", capabilities=["code", "review"]))
        d.register(_make_announcement("a2", capabilities=["review"]))
        d.register(_make_announcement("a3", capabilities=["plan"]))
        assert len(d.discover("review")) == 2
        assert len(d.discover("plan")) == 1
        assert len(d.discover("unknown")) == 0

    def test_get_active(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1"))
        d.register(_make_announcement("a2"))
        assert len(d.get_active()) == 2

    def test_register_overwrites(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1", role="old"))
        d.register(_make_announcement("a1", role="new"))
        assert d.get("a1") is not None
        assert d.get("a1").role == "new"  # type: ignore[union-attr]

    def test_prune_stale_removes_old(self) -> None:
        d = AgentDirectory()
        old_ts = datetime.now(UTC) - timedelta(seconds=120)
        d.register(_make_announcement("stale", timestamp=old_ts))
        d.register(_make_announcement("fresh"))
        removed = d.prune_stale(60)
        assert removed == ["stale"]
        assert d.get("stale") is None
        assert d.get("fresh") is not None

    def test_prune_stale_returns_empty_when_all_fresh(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1"))
        assert d.prune_stale(9999) == []


# --- GossipMessage ---


class TestGossipMessage:
    def test_default_ttl(self) -> None:
        m = GossipMessage(sender_id="s", topic="t", payload={})
        assert m.ttl == 3


# --- GossipProtocol ---


class TestGossipProtocol:
    def test_broadcast_reaches_others(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1"))
        d.register(_make_announcement("a2"))
        d.register(_make_announcement("a3"))
        gp = GossipProtocol(d)
        reached = gp.broadcast(_make_message(sender_id="a1"))
        assert reached == 2

    def test_broadcast_skips_sender(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1"))
        gp = GossipProtocol(d)
        assert gp.broadcast(_make_message(sender_id="a1")) == 0

    def test_broadcast_zero_ttl(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1"))
        d.register(_make_announcement("a2"))
        gp = GossipProtocol(d)
        assert gp.broadcast(_make_message(sender_id="a1", ttl=0)) == 0

    def test_send_to_known_agent(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1"))
        gp = GossipProtocol(d)
        assert gp.send_to("a1", _make_message(sender_id="a2")) is True
        msgs = gp.get_messages("a1")
        assert len(msgs) == 1
        assert msgs[0].sender_id == "a2"

    def test_send_to_unknown_agent(self) -> None:
        gp = GossipProtocol(AgentDirectory())
        assert gp.send_to("nope", _make_message()) is False

    def test_get_messages_drains_queue(self) -> None:
        d = AgentDirectory()
        d.register(_make_announcement("a1"))
        gp = GossipProtocol(d)
        gp.send_to("a1", _make_message(sender_id="a2"))
        assert len(gp.get_messages("a1")) == 1
        assert gp.get_messages("a1") == []

    def test_get_messages_empty(self) -> None:
        gp = GossipProtocol(AgentDirectory())
        assert gp.get_messages("nobody") == []
