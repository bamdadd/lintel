"""Chat router: classifies messages as direct chat replies or workflow triggers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.contracts.types import ModelPolicy
    from lintel.infrastructure.models.router import DefaultModelRouter

logger = structlog.get_logger()

WORKFLOW_KEYWORDS: dict[str, list[str]] = {
    "feature_to_pr": ["build", "implement", "create", "add feature", "new feature", "develop"],
    "bug_fix": ["fix", "bug", "broken", "error", "crash", "regression"],
    "refactor": ["refactor", "clean up", "modernize", "restructure", "simplify"],
    "code_review": ["review", "check code", "audit code", "look at the code"],
    "security_audit": ["security", "vulnerability", "cve", "penetration"],
    "documentation": ["document", "write docs", "update readme", "api docs"],
}


@dataclass(frozen=True)
class ChatRouterResult:
    """Result of classifying a chat message."""

    action: str  # "chat_reply" or "start_workflow"
    workflow_type: str = ""
    reply: str = ""


class ChatRouter:
    """Classifies chat messages and either replies directly or triggers a workflow."""

    def __init__(self, model_router: DefaultModelRouter | None = None) -> None:
        self._model_router = model_router

    async def classify(
        self,
        message: str,
        model_policy: ModelPolicy | None = None,
        api_base: str | None = None,
    ) -> ChatRouterResult:
        if self._model_router is not None:
            try:
                return await self._classify_with_llm(
                    message,
                    model_policy=model_policy,
                    api_base=api_base,
                )
            except Exception:
                logger.warning("llm_classify_failed, falling back to keywords")

        return self._classify_with_keywords(message)

    async def _classify_with_llm(
        self,
        message: str,
        model_policy: ModelPolicy | None = None,
        api_base: str | None = None,
    ) -> ChatRouterResult:
        from lintel.contracts.types import AgentRole

        assert self._model_router is not None
        if model_policy is not None:
            policy = model_policy
        else:
            policy = await self._model_router.select_model(AgentRole.TRIAGE, "classify")

        workflow_types = ", ".join(WORKFLOW_KEYWORDS.keys())
        result = await self._model_router.call_model(
            policy,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a message classifier for a software engineering platform. "
                        "Classify the user message as either a simple question/chat (reply "
                        "directly) or a task that requires a development workflow.\n\n"
                        "If it's a simple question, respond with:\n"
                        "ACTION: chat_reply\n"
                        "REPLY: <your helpful answer>\n\n"
                        "If it requires a workflow, respond with:\n"
                        f"ACTION: start_workflow\nWORKFLOW: <one of: {workflow_types}>\n"
                        "REPLY: <brief acknowledgment of what you'll do>\n\n"
                        "Examples of simple questions: 'what is a deadlock?', "
                        "'how does git rebase work?', 'explain CQRS'\n"
                        "Examples of workflow tasks: 'fix the login bug in auth.py', "
                        "'add a dark mode toggle to the settings page', "
                        "'refactor the database module'"
                    ),
                },
                {"role": "user", "content": message},
            ],
            api_base=api_base,
        )

        return self._parse_llm_response(result.get("content", ""))

    def _parse_llm_response(self, content: str) -> ChatRouterResult:
        action_match = re.search(r"ACTION:\s*(chat_reply|start_workflow)", content)
        workflow_match = re.search(r"WORKFLOW:\s*(\S+)", content)
        reply_match = re.search(r"REPLY:\s*(.+)", content, re.DOTALL)

        action = action_match.group(1) if action_match else "chat_reply"
        workflow_type = workflow_match.group(1).strip() if workflow_match else ""
        reply = reply_match.group(1).strip() if reply_match else content.strip()

        if action == "start_workflow" and workflow_type not in WORKFLOW_KEYWORDS:
            workflow_type = "feature_to_pr"

        return ChatRouterResult(action=action, workflow_type=workflow_type, reply=reply)

    def _classify_with_keywords(self, message: str) -> ChatRouterResult:
        lower = message.lower()

        # Short messages or questions are likely chat
        if len(lower.split()) < 4 or lower.rstrip("?").endswith(("what", "how", "why", "when")):
            return ChatRouterResult(
                action="chat_reply",
                reply="I can help with that, but AI responses aren't connected yet. "
                "This will be answered by the LLM once fully wired.",
            )

        # Check for workflow keywords
        for workflow_type, keywords in WORKFLOW_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return ChatRouterResult(
                    action="start_workflow",
                    workflow_type=workflow_type,
                    reply=f"Starting **{workflow_type.replace('_', ' ')}** workflow...",
                )

        # Default: treat longer messages as tasks
        if len(lower.split()) >= 8:
            return ChatRouterResult(
                action="start_workflow",
                workflow_type="feature_to_pr",
                reply="Starting **feature to PR** workflow...",
            )

        return ChatRouterResult(
            action="chat_reply",
            reply="I can help with that, but AI responses aren't connected yet. "
            "This will be answered by the LLM once fully wired.",
        )

    async def reply(
        self,
        message: str,
        model_policy: ModelPolicy | None = None,
        api_base: str | None = None,
    ) -> str:
        """Generate a direct chat reply using the LLM, or return a fallback."""
        if self._model_router is None:
            return (
                "AI responses aren't connected yet. "
                "Configure an AI provider to enable chat replies."
            )

        from lintel.contracts.types import AgentRole

        if model_policy is not None:
            policy = model_policy
        else:
            policy = await self._model_router.select_model(AgentRole.SUMMARIZER, "chat")
        result = await self._model_router.call_model(
            policy,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful software engineering assistant for the Lintel "
                        "platform. Give concise, accurate answers. If the user is asking "
                        "you to do development work (write code, fix bugs, etc.), tell them "
                        "to phrase it as a task so the workflow pipeline can handle it."
                    ),
                },
                {"role": "user", "content": message},
            ],
            api_base=api_base,
        )
        return str(result.get("content", "Sorry, I couldn't generate a response."))
