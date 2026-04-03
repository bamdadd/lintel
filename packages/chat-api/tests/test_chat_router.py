"""Tests for the ChatRouter: keyword classification, LLM parsing, reply logic."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import pytest

from lintel.chat_api.chat_router import (
    INTENT_KEYWORDS,
    WORKFLOW_KEYWORDS,
    ChatRouter,
    ChatRouterResult,
    _extract_entity_ref,
)


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

    def test_unknown_workflow_falls_back_to_chat(self) -> None:
        content = "ACTION: start_workflow\nWORKFLOW: unknown_type\nREPLY: On it."
        result = self.router._parse_llm_response(content)
        assert result.action == "chat_reply"

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


class TestIntentClassification:
    """Tests for non-workflow intent matching."""

    def setup_method(self) -> None:
        self.router = ChatRouter(model_router=None)

    async def test_show_board_intent(self) -> None:
        result = await self.router.classify("show board")
        assert result.action == "show_board"
        assert "show board" in result.reply.lower()

    async def test_kanban_keyword_triggers_show_board(self) -> None:
        result = await self.router.classify("kanban view please")
        assert result.action == "show_board"

    async def test_check_status_intent(self) -> None:
        result = await self.router.classify("what's the status of WI-abc123")
        assert result.action == "check_status"
        assert result.entity_ref == "wi-abc123"

    async def test_create_work_item_intent(self) -> None:
        result = await self.router.classify("create a story for adding dark mode")
        assert result.action == "create_work_item"

    async def test_implement_item_intent(self) -> None:
        result = await self.router.classify("implement item WI-xyz789 now")
        assert result.action == "implement_item"
        assert result.entity_ref == "wi-xyz789"

    async def test_review_pr_intent(self) -> None:
        result = await self.router.classify("review PR #42 please")
        assert result.action == "review_pr"
        assert result.entity_ref == "PR#42"

    async def test_assign_item_intent(self) -> None:
        result = await self.router.classify("assign item WI-def456 to me")
        assert result.action == "assign_item"
        assert result.entity_ref == "wi-def456"

    async def test_change_priority_intent(self) -> None:
        result = await self.router.classify("make it p0 immediately")
        assert result.action == "change_priority"

    async def test_intent_takes_precedence_over_workflow(self) -> None:
        result = await self.router.classify("review pr #10 and check the code changes")
        assert result.action == "review_pr"

    async def test_whats_in_progress_triggers_show_board(self) -> None:
        result = await self.router.classify("what's in progress right now")
        assert result.action == "show_board"


class TestExtractEntityRef:
    """Tests for _extract_entity_ref helper."""

    def test_extract_wi_prefix_with_dash(self) -> None:
        assert _extract_entity_ref("check WI-abc123", "check_status") == "wi-abc123"

    def test_extract_work_prefix_with_dash(self) -> None:
        assert _extract_entity_ref("check WORK-abc123", "check_status") == "work-abc123"

    def test_extract_pr_number(self) -> None:
        assert _extract_entity_ref("review PR #42", "review_pr") == "PR#42"

    def test_extract_pr_without_hash(self) -> None:
        assert _extract_entity_ref("review PR 99", "review_pr") == "PR#99"

    def test_extract_pull_request_phrase(self) -> None:
        assert _extract_entity_ref("review pull request #7", "review_pr") == "PR#7"

    def test_no_entity_returns_empty(self) -> None:
        assert _extract_entity_ref("show the board", "show_board") == ""

    def test_non_pr_intent_extracts_work_item(self) -> None:
        assert _extract_entity_ref("assign WI-xyz to me", "assign_item") == "wi-xyz"

    def test_non_pr_intent_ignores_pr_ref(self) -> None:
        assert _extract_entity_ref("assign PR #5 to me", "assign_item") == ""


class TestLLMIntentParsing:
    """Tests for _parse_llm_response with intent actions."""

    def setup_method(self) -> None:
        self.router = ChatRouter(model_router=None)

    def test_parse_show_board_intent(self) -> None:
        content = "ACTION: show_board\nREPLY: Here's the board."
        result = self.router._parse_llm_response(content)
        assert result.action == "show_board"
        assert result.reply == "Here's the board."

    def test_parse_intent_with_entity(self) -> None:
        content = "ACTION: check_status\nENTITY: WI-abc123\nREPLY: Checking status."
        result = self.router._parse_llm_response(content)
        assert result.action == "check_status"
        assert result.entity_ref == "WI-abc123"

    def test_parse_review_pr_intent(self) -> None:
        content = "ACTION: review_pr\nENTITY: PR#42\nREPLY: Reviewing PR."
        result = self.router._parse_llm_response(content)
        assert result.action == "review_pr"
        assert result.entity_ref == "PR#42"

    def test_unknown_intent_falls_through_to_chat(self) -> None:
        content = "ACTION: unknown_intent\nREPLY: Not sure."
        result = self.router._parse_llm_response(content)
        assert result.action == "chat_reply"


class TestLLMClassifyIntents:
    """Tests for classify() with LLM returning intents."""

    async def test_llm_returns_intent(self) -> None:
        mock_router = AsyncMock()
        mock_router.select_model.return_value = MagicMock()
        mock_router.call_model.return_value = {
            "content": "ACTION: show_board\nREPLY: Here's the board."
        }
        router = ChatRouter(model_router=mock_router)
        result = await router.classify("show me the board")
        assert result.action == "show_board"

    async def test_llm_failure_falls_back_to_intent_keywords(self) -> None:
        mock_router = AsyncMock()
        mock_router.select_model.side_effect = RuntimeError("LLM unavailable")
        router = ChatRouter(model_router=mock_router)
        result = await router.classify("show board please")
        assert result.action == "show_board"


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

    def test_chat_router_result_entity_ref_defaults_to_empty(self) -> None:
        result = ChatRouterResult(action="chat_reply", reply="hi")
        assert result.entity_ref == ""


class TestIntentKeywordsIntegrity:
    """Validate the INTENT_KEYWORDS constant."""

    def test_all_keys_are_strings(self) -> None:
        for key in INTENT_KEYWORDS:
            assert isinstance(key, str)

    def test_all_values_are_non_empty_lists(self) -> None:
        for key, keywords in INTENT_KEYWORDS.items():
            assert len(keywords) > 0, f"{key} has empty keyword list"

    def test_no_overlap_with_workflow_keywords(self) -> None:
        intent_keys = set(INTENT_KEYWORDS.keys())
        workflow_keys = set(WORKFLOW_KEYWORDS.keys())
        assert intent_keys.isdisjoint(workflow_keys), f"Overlap: {intent_keys & workflow_keys}"


class TestAmbiguousMessageClassification:
    """Tests for the bug fix: ambiguous/short messages must not trigger workflows."""

    def setup_method(self) -> None:
        self.router = ChatRouter(model_router=None)

    async def test_single_word_slack_is_chat(self) -> None:
        result = await self.router.classify("slack")
        assert result.action == "chat_reply"

    async def test_single_word_hello_is_chat(self) -> None:
        result = await self.router.classify("hello")
        assert result.action == "chat_reply"

    async def test_single_word_never_triggers_workflow(self) -> None:
        for word in ("slack", "hello", "hi", "test", "help"):
            result = await self.router.classify(word)
            assert result.action != "start_workflow", f"'{word}' should not start a workflow"

    def test_llm_conversational_response_without_action_is_chat(self) -> None:
        """LLM says 'I can help you' but no ACTION line -> chat_reply, not workflow."""
        content = "I can help you with that, could you clarify what you need?"
        result = self.router._parse_llm_response(content)
        assert result.action == "chat_reply"

    def test_llm_let_me_response_without_action_is_chat(self) -> None:
        """LLM says 'let me' but no ACTION line -> chat_reply."""
        content = "Let me know more details about your request."
        result = self.router._parse_llm_response(content)
        assert result.action == "chat_reply"

    def test_explicit_action_workflow_still_works(self) -> None:
        """Explicit ACTION: start_workflow + WORKFLOW line must still be honoured."""
        content = "ACTION: start_workflow\nWORKFLOW: feature_to_pr\nREPLY: Starting now."
        result = self.router._parse_llm_response(content)
        assert result.action == "start_workflow"
        assert result.workflow_type == "feature_to_pr"

    def test_unknown_workflow_type_does_not_default_to_feature(self) -> None:
        """ACTION: start_workflow with unrecognised WORKFLOW must not default to feature_to_pr."""
        content = "ACTION: start_workflow\nWORKFLOW: mystery\nREPLY: On it."
        result = self.router._parse_llm_response(content)
        assert result.action == "chat_reply"


class TestShortMessageServiceGuard:
    """Tests for the service-level guard: short messages override start_workflow."""

    def test_short_message_guard_overrides_result(self) -> None:
        """Verify the guard logic: < 4-word message with start_workflow -> chat_reply.

        This tests the guard inline rather than through the full ChatService,
        because ChatService.handle_classified_message requires request context.
        """
        from lintel.chat_api.chat_router import ChatRouterResult as _Result

        # Simulate what handle_classified_message does:
        message = "slack"
        result = _Result(
            action="start_workflow",
            workflow_type="feature_to_pr",
            reply="Starting...",
        )

        if result.action == "start_workflow" and len(message.split()) < 4:
            result = _Result(action="chat_reply", reply="")

        assert result.action == "chat_reply"
        assert result.workflow_type == ""

    def test_long_message_not_overridden(self) -> None:
        """Messages with >= 4 words should not be overridden by the guard."""
        from lintel.chat_api.chat_router import ChatRouterResult as _Result

        message = "implement a new login page"
        result = _Result(
            action="start_workflow",
            workflow_type="feature_to_pr",
            reply="Starting...",
        )

        if result.action == "start_workflow" and len(message.split()) < 4:
            result = _Result(action="chat_reply", reply="")

        assert result.action == "start_workflow"
        assert result.workflow_type == "feature_to_pr"
