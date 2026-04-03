"""Types for context injection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextSnippet:
    """A ranked code snippet with metadata."""

    file_path: str
    content: str
    score: float = 0.0
    language: str = ""
    start_line: int = 0
    end_line: int = 0
    token_estimate: int = 0


@dataclass(frozen=True)
class ContextBudget:
    """Token budget configuration for context injection."""

    max_tokens: int = 8000
    reserved_for_system: int = 1000
    reserved_for_user: int = 1000

    @property
    def available_tokens(self) -> int:
        return max(0, self.max_tokens - self.reserved_for_system - self.reserved_for_user)


@dataclass(frozen=True)
class InjectedContext:
    """The result of context injection — ranked and trimmed snippets."""

    snippets: tuple[ContextSnippet, ...] = ()
    file_paths: tuple[str, ...] = ()
    architectural_summary: str = ""
    total_tokens: int = 0
    trimmed_count: int = 0

    @property
    def as_prompt_section(self) -> str:
        """Format as a prompt section for injection into agent system prompts."""
        if not self.snippets:
            return ""
        parts: list[str] = []
        if self.architectural_summary:
            parts.append(f"## Architectural Context\n{self.architectural_summary}")
        if self.file_paths:
            parts.append("## Relevant Files\n" + "\n".join(f"- `{p}`" for p in self.file_paths))
        for snippet in self.snippets:
            header = f"### {snippet.file_path}"
            if snippet.start_line:
                header += f" (L{snippet.start_line}-{snippet.end_line})"
            lang = snippet.language or ""
            parts.append(f"{header}\n```{lang}\n{snippet.content}\n```")
        if self.trimmed_count > 0:
            parts.append(
                f"*({self.trimmed_count} additional snippet(s) omitted due to token budget)*"
            )
        return "\n\n".join(parts)
