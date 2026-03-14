"""Branch naming convention helpers."""

from __future__ import annotations

import re
from typing import ClassVar


class BranchNaming:
    """Encapsulates branch naming conventions."""

    _TYPE_MAP: ClassVar[dict[str, str]] = {
        "feature": "feat",
        "bug": "fix",
        "refactor": "refactor",
    }

    _MAX_SLUG_LEN = 40

    @classmethod
    def generate(
        cls,
        work_item_id: str,
        work_type: str = "feat",
        description: str = "",
    ) -> str:
        """Generate a branch name following convention: lintel/<type>/<id>-<slug>.

        Rules:
        - *type* is mapped via ``_TYPE_MAP`` (feature->feat, bug->fix, …); unknown
          types fall back to ``"task"``.
        - The *work_item_id* is truncated to 8 characters.
        - *description* is slugified: lowercased, non-alphanumeric replaced with
          hyphens, truncated to 40 chars, trailing hyphens stripped.
        - If no description is given the branch is ``lintel/<type>/<id>``.
        """
        branch_type = cls._TYPE_MAP.get(
            work_type, work_type if work_type in cls._TYPE_MAP.values() else "task"
        )
        short_id = work_item_id[:8]

        if not description:
            return f"lintel/{branch_type}/{short_id}"

        slug = description.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        slug = slug[: cls._MAX_SLUG_LEN].rstrip("-")

        return f"lintel/{branch_type}/{short_id}-{slug}"


# Backward-compatible wrapper
_TYPE_MAP = BranchNaming._TYPE_MAP
_MAX_SLUG_LEN = BranchNaming._MAX_SLUG_LEN


def generate_branch_name(
    work_item_id: str,
    work_type: str = "feat",
    description: str = "",
) -> str:
    """Generate a branch name following convention: lintel/<type>/<id>-<slug>.

    Backward-compatible wrapper around :class:`BranchNaming`.
    """
    return BranchNaming.generate(work_item_id, work_type, description)
