"""Tests for InMemorySlackBotStore."""

from lintel.multi_slack_bot_api.store import InMemorySlackBotStore, SlackBot


class TestInMemorySlackBotStore:
    async def test_find_by_signing_secret(self) -> None:
        store = InMemorySlackBotStore()
        bot = SlackBot(
            bot_id="b1",
            name="B1",
            signing_secret="sec-1",
            bot_token="t1",
        )
        await store.add(bot)

        found = await store.find_by_signing_secret("sec-1")
        assert found is not None
        assert found.bot_id == "b1"

    async def test_find_by_signing_secret_not_found(self) -> None:
        store = InMemorySlackBotStore()
        assert await store.find_by_signing_secret("nope") is None

    async def test_find_by_signing_secret_skips_disabled(self) -> None:
        store = InMemorySlackBotStore()
        bot = SlackBot(
            bot_id="b2",
            name="B2",
            signing_secret="sec-2",
            bot_token="t2",
            enabled=False,
        )
        await store.add(bot)
        assert await store.find_by_signing_secret("sec-2") is None

    async def test_find_by_token(self) -> None:
        store = InMemorySlackBotStore()
        bot = SlackBot(bot_id="b3", name="B3", bot_token="xoxb-abc")
        await store.add(bot)

        found = await store.find_by_token("xoxb-abc")
        assert found is not None
        assert found.bot_id == "b3"

    async def test_find_by_token_not_found(self) -> None:
        store = InMemorySlackBotStore()
        assert await store.find_by_token("nope") is None

    async def test_project_and_workflow_bindings(self) -> None:
        store = InMemorySlackBotStore()
        bot = SlackBot(
            bot_id="b4",
            name="B4",
            bot_token="t4",
            project_bindings=["p1", "p2"],
            workflow_bindings=["wf1"],
        )
        await store.add(bot)

        result = await store.get("b4")
        assert result is not None
        assert result.project_bindings == ["p1", "p2"]
        assert result.workflow_bindings == ["wf1"]
