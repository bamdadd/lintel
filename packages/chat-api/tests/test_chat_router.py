"""Tests for the ChatRouter: keyword classification, LLM parsing, reply logic."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import pytest

from lintel.chat_api.chat_router import WORKFLOW_KEYWORDS, ChatRouter, ChatRouterResult


class TestKeywordClassification:
    """Tests for _classify_with_keywords (no LLM)."""

    def setup_method(self) -> None:
        self.router = ChatRouter(model_router=None)

    async def test_short_message_is_chat(self) -> None:
        result = await self.router.classify("hello there")
        assert result.action == "chat_reply"

    async def test_question_ending_what_is_chat(self) -> None:
        result = await self.router.classify("explain what")
        assert result.action == "chat_reply"

    async def test_question_ending_how_is_chat(self) -> None:
        result = await self.router.classify("explain how")
        assert result.action == "chat_reply"

    async def test_bug_keyword_triggers_bug_fix(self) -> None:
        result = await self.router.classify("there is a bug in the auth module please fix it")
        assert result.action == "start_workflow"
        assert result.workflow_type == "bug_fix"

    async def test_fix_keyword_triggers_bug_fix(self) -> None:
        result = await self.router.classify("please fix the broken login page now")
        assert result.action == "start_workflow"
        assert result.workflow_type == "bug_fix"

    async def test_refactor_keyword_triggers_refactor(self) -> None:
        result = await self.router.classify("refactor the database module to use async")
        assert result.action == "start_workflow"
        assert result.workflow_type == "refactor"

    async def test_implement_keyword_triggers_feature(self) -> None:
        result = await self.router.classify("implement a dark mode toggle in settings")
        assert result.action == "start_workflow"
        assert result.workflow_type == "feature_to_pr"

    async def test_review_keyword_triggers_code_review(self) -> None:
        result = await self.router.classify("review the code changes in the PR for auth")
        assert result.action == "start_workflow"
        assert result.workflow_type == "code_review"

    async def test_security_keyword_triggers_security_audit(self) -> None:
        result = await self.router.classify("run a security scan on the entire codebase now")
        assert result.action == "start_workflow"
        assert result.workflow_type == "security_audit"

    async def test_documentation_keyword_triggers_docs(self) -> None:
        result = await self.router.classify("document the API endpoints for the new service")
        assert result.action == "start_workflow"
        assert result.workflow_type == "documentation"

    async def test_long_message_without_keywords_defaults_to_feature(self) -> None:
        result = await self.router.classify(
            "please add a new page to the dashboard that shows the analytics data in charts"
        )
        assert result.action == "start_workflow"
        assert result.workflow_type == "feature_to_pr"

    async def test_medium_message_without_keywords_is_chat(self) -> None:
        result = await self.router.classify("what is CQRS pattern")
        assert result.action == "chat_reply"

    async def test_reply_text_is_set(self) -> None:
        result = await self.router.classify("fix the login bug in auth module please")
        assert "bug fix" in result.reply.lower()


class TestLLMResponseParsing:
    """Tests for _parse_llm_response."""

    def setup_method(self) -> None:
        self.router = ChatRouter(model_router=None)

    def test_parse_chat_reply(self) -> None:
        content = "ACTION: chat_reply\nREPLY: A deadlock is when two threads wait for each other."
        result = self.router._parse_llm_response(content)
        assert result.action == "chat_reply"
        assert "deadlock" in result.reply

    def test_parse_start_workflow(self) -> None:
        content = "ACTION: start_workflow\nWORKFLOW: bug_fix\nREPLY: I'll fix that bug."
        result = self.router._parse_llm_response(content)
        assert result.action == "start_workflow"
        assert result.workflow_type == "bug_fix"
        assert "fix" in result.reply.lower()

    def test_unknown_workflow_defaults_to_feature(self) -> None:
        content = "ACTION: start_workflow\nWORKFLOW: unknown_type\nREPLY: On it."
        result = self.router._parse_llm_response(content)
        assert result.action == "start_workflow"
        assert result.workflow_type == "feature_to_pr"

    def test_missing_action_defaults_to_chat(self) -> None:
        content = "I'm not sure what to do with this."
        result = self.router._parse_llm_response(content)
        assert result.action == "chat_reply"

    def test_missing_reply_uses_content(self) -> None:
        content = "ACTION: chat_reply"
        result = self.router._parse_llm_response(content)
        assert result.reply == "ACTION: chat_reply"

    def test_multiline_reply(self) -> None:
        content = "ACTION: chat_reply\nREPLY: Line one.\nLine two."
        result = self.router._parse_llm_response(content)
        assert "Line one" in result.reply
        assert "Line two" in result.reply


class TestClassifyWithLLM:
    """Tests for classify() with a model router (LLM path)."""

    async def test_llm_classify_success(self) -> None:
        mock_router = AsyncMock()
        mock_router.select_model.return_value = MagicMock()
        mock_router.call_model.return_value = {
            "content": "ACTION: start_workflow\nWORKFLOW: bug_fix\nREPLY: Fixing it."
        }
        router = ChatRouter(model_router=mock_router)
        result = await router.classify("fix the login bug")
        assert result.action == "start_workflow"
        assert result.workflow_type == "bug_fix"

    async def test_llm_failure_falls_back_to_keywords(self) -> None:
        mock_router = AsyncMock()
        mock_router.select_model.side_effect = RuntimeError("LLM unavailable")
        router = ChatRouter(model_router=mock_router)
        result = await router.classify("fix the broken login page for users")
        assert result.action == "start_workflow"
        assert result.workflow_type == "bug_fix"

    async def test_classify_with_explicit_policy(self) -> None:
        mock_router = AsyncMock()
        mock_router.call_model.return_value = {"content": "ACTION: chat_reply\nREPLY: Hello!"}
        from lintel.models.types import ModelPolicy

        policy = ModelPolicy("test", "test-model", 100, 0.0)
        router = ChatRouter(model_router=mock_router)
        result = await router.classify("hi", model_policy=policy)
        assert result.action == "chat_reply"
        mock_router.select_model.assert_not_called()


class TestReply:
    """Tests for reply() and reply_stream()."""

    async def test_reply_without_router_returns_fallback(self) -> None:
        router = ChatRouter(model_router=None)
        result = await router.reply("hello")
        assert "aren't connected" in result

    async def test_reply_with_router_calls_model(self) -> None:
        mock_router = AsyncMock()
        mock_router.select_model.return_value = MagicMock()
        mock_router.call_model.return_value = {"content": "Here's the answer."}
        router = ChatRouter(model_router=mock_router)
        result = await router.reply("what is CQRS?")
        assert result == "Here's the answer."

    async def test_reply_stream_without_router_yields_fallback(self) -> None:
        router = ChatRouter(model_router=None)
        tokens = [t async for t in router.reply_stream("hello")]
        assert len(tokens) == 1
        assert "aren't connected" in tokens[0]

    async def test_reply_stream_with_router(self) -> None:
        mock_router = AsyncMock()
        mock_router.select_model.return_value = MagicMock()

        async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[str]:
            for token in ["Hello", " world"]:
                yield token

        mock_router.stream_model = fake_stream
        router = ChatRouter(model_router=mock_router)
        tokens = [t async for t in router.reply_stream("hi")]
        assert tokens == ["Hello", " world"]


class TestWorkflowKeywordsIntegrity:
    """Validate the WORKFLOW_KEYWORDS constant."""

    def test_all_keys_are_strings(self) -> None:
        for key in WORKFLOW_KEYWORDS:
            assert isinstance(key, str)

    def test_all_values_are_non_empty_lists(self) -> None:
        for key, keywords in WORKFLOW_KEYWORDS.items():
            assert len(keywords) > 0, f"{key} has empty keyword list"

    def test_chat_router_result_is_frozen(self) -> None:
        result = ChatRouterResult(action="chat_reply", reply="hi")
        with pytest.raises(AttributeError):
            result.action = "other"  # type: ignore[misc]
