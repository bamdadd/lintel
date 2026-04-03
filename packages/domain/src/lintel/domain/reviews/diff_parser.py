"""Simple unified diff parser for extracting changed files and line info."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DiffHunk:
    """A single hunk within a diff showing changed line ranges."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str = ""


@dataclass(frozen=True)
class DiffFile:
    """A file extracted from a unified diff."""

    path: str
    added_lines: tuple[int, ...] = ()
    removed_lines: tuple[int, ...] = ()
    hunks: tuple[DiffHunk, ...] = ()


_DIFF_HEADER = re.compile(r"^diff --git a/.+ b/(.+)$")
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_diff(diff_text: str) -> list[DiffFile]:
    """Parse a unified diff into a list of :class:`DiffFile` instances.

    Only processes ``diff --git`` style diffs. Each file includes the hunks
    with added/removed line numbers based on the new-file side.
    """
    files: list[DiffFile] = []
    current_path: str | None = None
    current_hunks: list[DiffHunk] = []
    current_added: list[int] = []
    current_removed: list[int] = []
    _new_line = 0
    _old_line = 0

    def _flush() -> None:
        nonlocal current_path, current_hunks, current_added, current_removed
        if current_path is not None:
            files.append(
                DiffFile(
                    path=current_path,
                    added_lines=tuple(current_added),
                    removed_lines=tuple(current_removed),
                    hunks=tuple(current_hunks),
                )
            )
        current_path = None
        current_hunks = []
        current_added = []
        current_removed = []

    for line in diff_text.splitlines():
        header_match = _DIFF_HEADER.match(line)
        if header_match:
            _flush()
            current_path = header_match.group(1)
            continue

        hunk_match = _HUNK_HEADER.match(line)
        if hunk_match:
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2) or "1")
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4) or "1")
            current_hunks.append(
                DiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    content=line,
                )
            )
            # Track line numbers within the hunk
            _new_line = new_start
            _old_line = old_start
            continue

        if current_path is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current_added.append(_new_line)
            _new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            current_removed.append(_old_line)
            _old_line += 1
        else:
            # Context line — both sides advance
            _new_line += 1
            _old_line += 1

    _flush()
    return files
