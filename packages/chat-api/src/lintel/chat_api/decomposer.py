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

_WORK_TYPE_MAP: dict[str, WorkItemType] = {
    "feature": WorkItemType.FEATURE,
    "bug": WorkItemType.BUG,
    "refactor": WorkItemType.REFACTOR,
    "task": WorkItemType.TASK,
}

DECOMPOSE_SYSTEM_PROMPT = """\
You are a software project planner. Given an idea description and optional project \
context, decompose the idea into 3-10 concrete, right-sized work items suitable for \
an AI coding agent to implement one at a time.

Each work item should be small enough for a single feature branch / pull request.

Respond with a JSON array. Each element must have:
- "title": short imperative title (max 100 chars)
- "description": 2-4 sentence description with acceptance criteria
- "work_type": one of "feature", "bug", "refactor", "task"
- "order": integer 1..N indicating suggested implementation order

Example response:
```json
[
  {
    "title": "Add FooBar data model and store",
    "description": "Create the FooBar dataclass in domain/types.py with fields x, y, z. \\
Add an in-memory store. Acceptance: unit tests pass for CRUD operations.",
    "work_type": "feature",
    "order": 1
  }
]
```

IMPORTANT:
- Output ONLY the JSON array, no other text.
- Keep titles action-oriented and concise.
- Descriptions should include enough context for an implementer.
- Order items so dependencies come first.
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
        except json.JSONDecodeError:
            logger.warning("decompose_parse_failed", content=content[:500])
            return []

        if not isinstance(items_raw, list):
            logger.warning("decompose_response_not_list", content=content[:500])
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
