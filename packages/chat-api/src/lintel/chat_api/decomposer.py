"""Idea decomposition: breaks a natural language idea into structured work items."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from lintel.models.router import DefaultModelRouter
    from lintel.models.types import ModelPolicy
    from lintel.work_items_api.store import WorkItemStore

from lintel.domain.types import WorkItem, WorkItemStatus, WorkItemType

logger = structlog.get_logger()


def _try_salvage_partial_json(text: str) -> list[dict[str, Any]] | None:
    """Attempt to recover complete items from truncated JSON array.

    When the LLM output is cut off mid-response, we try to find the last
    complete JSON object in the array and parse everything up to that point.
    """
    # Find the last complete object boundary: "},\n  {" or "}\n]"
    last_complete = -1
    brace_depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0:
                last_complete = i

    if last_complete <= 0:
        return None

    # Truncate at the last complete object and close the array
    truncated = text[: last_complete + 1].rstrip().rstrip(",") + "\n]"
    try:
        parsed = json.loads(truncated)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass
    return None


_WORK_TYPE_MAP: dict[str, WorkItemType] = {
    "feature": WorkItemType.FEATURE,
    "bug": WorkItemType.BUG,
    "refactor": WorkItemType.REFACTOR,
    "task": WorkItemType.TASK,
}

DECOMPOSE_SYSTEM_PROMPT = """\
You are a software project planner decomposing ideas into work items for an \
autonomous AI coding agent. The agent will implement each work item independently \
via a feature_to_pr pipeline (research → plan → implement → review → PR) with NO \
human clarification available.

## Sizing constraint

Each work item MUST be implementable in a single pull request touching at most \
3 files:
- One cohesive concern — never bundle unrelated changes
- If a concept needs both an interface/protocol AND an implementation, split them \
into separate work items (interface first)

## Requirement traceability

Every numbered point, feature, or distinct capability mentioned in the user's idea \
MUST map to at least one work item. Do NOT silently drop requirements. If the idea \
lists 9 things, produce at least 9 work items.

## Interface-first ordering

- Protocols and abstractions MUST appear before concrete implementations
- Foundation first: project scaffold, shared types/protocols, configuration
- Define interfaces before concrete adapters
- Data layer before API layer before UI layer
- Cross-cutting concerns (multi-tenancy, auth, event sourcing) early

## Agent-ready descriptions

Each description MUST include ALL of the following so the agent can implement \
without asking questions:
1. Target package and key files to create or modify
2. Key types, classes, or functions to implement (with field names where relevant)
3. API routes with HTTP methods and paths (if applicable)
4. Events to emit (if the project uses event sourcing)
5. Acceptance tests: specific criteria an agent can verify
6. What is explicitly OUT OF SCOPE for this work item

## Output format

Respond with a JSON array. Each element must have:
- "title": short imperative title (max 100 chars)
- "description": detailed description following the agent-ready rules above
- "work_type": one of "feature", "bug", "refactor", "task"
- "order": integer 1..N indicating implementation order respecting dependencies

IMPORTANT:
- Output ONLY the JSON array, no other text.
- Keep titles action-oriented and concise.
- Order items so dependencies come first.
- Prefer more smaller items over fewer large ones.
"""


@dataclass(frozen=True)
class DecomposedItem:
    """A single work item produced by idea decomposition."""

    title: str
    description: str
    work_type: WorkItemType
    order: int


class IdeaDecomposer:
    """Decomposes a natural language idea into structured work items."""

    def __init__(
        self,
        model_router: DefaultModelRouter,
    ) -> None:
        self._model_router = model_router

    async def decompose(
        self,
        idea: str,
        model_policy: ModelPolicy | None = None,
        api_base: str | None = None,
        project_context: str = "",
    ) -> list[DecomposedItem]:
        """Call the LLM to decompose an idea into work items."""
        from lintel.agents.types import AgentRole

        if model_policy is None:
            model_policy = await self._model_router.select_model(AgentRole.PLANNER, "decompose")

        user_content = f"Idea: {idea}"
        if project_context:
            user_content = f"Project context:\n{project_context}\n\n{user_content}"

        # Decomposition produces detailed JSON — ensure enough output tokens.
        # Override policy max_tokens if it's too low for structured output.
        from dataclasses import replace as dc_replace

        min_decompose_tokens = 8192
        if model_policy.max_tokens < min_decompose_tokens:
            model_policy = dc_replace(model_policy, max_tokens=min_decompose_tokens)

        result = await self._model_router.call_model(
            model_policy,
            messages=[
                {"role": "system", "content": DECOMPOSE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            api_base=api_base,
        )

        content = str(result.get("content", ""))
        return self._parse_response(content)

    @staticmethod
    def _parse_response(content: str) -> list[DecomposedItem]:
        """Parse the LLM response JSON into DecomposedItem list."""
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`")

        try:
            items_raw: list[dict[str, Any]] = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Try to salvage partial JSON (truncated LLM response)
            items_raw = _try_salvage_partial_json(cleaned)
            if items_raw is None:
                logger.warning(
                    "decompose_parse_failed",
                    error=str(exc),
                    content_length=len(content),
                    content_preview=content[:500],
                )
                return []
            logger.info(
                "decompose_salvaged_partial_json",
                salvaged_items=len(items_raw),
                content_length=len(content),
            )

        if not isinstance(items_raw, list):
            logger.warning(
                "decompose_response_not_list",
                actual_type=type(items_raw).__name__,
                content_preview=content[:500],
            )
            return []

        items: list[DecomposedItem] = []
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title", ""))[:100]
            description = str(raw.get("description", ""))
            work_type_str = str(raw.get("work_type", "task")).lower()
            work_type = _WORK_TYPE_MAP.get(work_type_str, WorkItemType.TASK)
            order = int(raw.get("order", len(items) + 1))
            if title:
                items.append(
                    DecomposedItem(
                        title=title,
                        description=description,
                        work_type=work_type,
                        order=order,
                    )
                )

        items.sort(key=lambda x: x.order)
        return items

    @staticmethod
    async def create_work_items(
        items: list[DecomposedItem],
        project_id: str,
        work_item_store: WorkItemStore,
    ) -> list[str]:
        """Persist decomposed items as work items on the board.

        Returns the list of created work item IDs.
        """
        created_ids: list[str] = []
        for i, item in enumerate(items):
            work_item_id = str(uuid4())
            work_item = WorkItem(
                work_item_id=work_item_id,
                project_id=project_id,
                title=item.title,
                description=item.description,
                work_type=item.work_type,
                status=WorkItemStatus.OPEN,
                column_position=i,
            )
            try:
                await work_item_store.add(work_item)
                created_ids.append(work_item_id)
            except Exception:
                logger.warning(
                    "decompose_work_item_creation_failed",
                    title=item.title,
                    work_item_id=work_item_id,
                )
        return created_ids

    @staticmethod
    def format_reply(items: list[DecomposedItem], created_count: int) -> str:
        """Build a user-friendly reply summarising created work items."""
        if not items:
            return (
                "I couldn't break that idea into work items. "
                "Could you provide more detail about what you'd like to build?"
            )

        lines = [
            f"Decomposed your idea into **{created_count}** work items:\n",
        ]
        for item in items:
            type_label = item.work_type.value
            lines.append(f"  {item.order}. **{item.title}** ({type_label})")
            if item.description:
                # Show first sentence of description
                first_sentence = item.description.split(". ")[0]
                lines.append(f"     _{first_sentence}_")

        lines.append(
            "\nAll items are on the board as **open**. "
            "Move them to **in_progress** to start implementation."
        )
        return "\n".join(lines)
