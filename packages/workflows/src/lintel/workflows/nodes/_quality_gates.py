"""Quality gates for pipeline node outputs."""

from __future__ import annotations

import re
from typing import Any

REQUIRED_RESEARCH_SECTIONS = [
    "## Relevant Files",
    "## Current Architecture",
    "## Key Patterns",
    "## Impact Analysis",
    "## Recommendations",
]

_FILE_PATH_RE = re.compile(r"[\w./\-]+\.\w{1,10}")


def validate_research_report(content: str) -> list[str]:
    """Validate a research report has required structure.

    Returns list of errors (empty = valid).
    """
    errors: list[str] = []

    if len(content) < 500:
        errors.append(f"Report too short ({len(content)} chars, minimum 500)")

    for section in REQUIRED_RESEARCH_SECTIONS:
        if section not in content:
            errors.append(f"Missing section: {section}")

    file_refs = _FILE_PATH_RE.findall(content)
    if len(file_refs) < 3:
        errors.append(f"Too few file path references ({len(file_refs)}, minimum 3)")

    return errors


def validate_plan(plan: dict[str, Any]) -> list[str]:
    """Validate a parsed plan has required structure.

    Returns list of errors (empty = valid).
    """
    errors: list[str] = []

    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or len(tasks) < 2:
        count = len(tasks) if isinstance(tasks, list) else 0
        errors.append(f"Plan must have at least 2 tasks (got {count})")
        return errors  # Can't validate tasks further

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"Task {i + 1} is not a dict")
            continue
        if not task.get("title"):
            errors.append(f"Task {i + 1} missing 'title'")
        if not task.get("description"):
            errors.append(f"Task {i + 1} missing 'description'")
        file_paths = task.get("file_paths")
        if not isinstance(file_paths, list) or not file_paths:
            errors.append(f"Task {i + 1} missing or empty 'file_paths'")

    summary = plan.get("summary")
    if not summary or not isinstance(summary, str):
        errors.append("Plan missing 'summary'")

    return errors
