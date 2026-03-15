"""Tests for Claude model detection in implement node."""

from __future__ import annotations

import pytest

from lintel.workflows.nodes.implement import _is_claude_model


class TestIsClaudeModel:
    @pytest.mark.parametrize(
        ("provider", "model_name", "expected"),
        [
            # Claude Code provider — always TDD
            ("claude_code", "claude-code", True),
            ("claude_code", "anything", True),
            # Bedrock Claude models — TDD
            ("bedrock", "anthropic.claude-sonnet-4-6", True),
            ("bedrock", "eu.anthropic.claude-sonnet-4-6", True),
            ("bedrock", "us.anthropic.claude-sonnet-4-6", True),
            ("bedrock", "anthropic.claude-3-5-sonnet-20241022-v2:0", True),
            ("bedrock", "eu.anthropic.claude-3-5-haiku-20241022-v1:0", True),
            # Anthropic API — TDD
            ("anthropic", "claude-sonnet-4-6", True),
            ("anthropic", "claude-3-5-sonnet-latest", True),
            # Non-Claude models — structured path
            ("bedrock", "amazon.nova-pro-v1:0", False),
            ("bedrock", "meta.llama3-70b-instruct-v1:0", False),
            ("ollama", "qwen2.5-coder:32b", False),
            ("ollama", "llama3.1:70b", False),
            ("openai", "gpt-4o", False),
            ("litellm", "deepseek-coder", False),
        ],
    )
    def test_detection(self, provider: str, model_name: str, expected: bool) -> None:
        assert _is_claude_model(provider, model_name) == expected
