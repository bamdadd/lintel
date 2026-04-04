"""Repo selector engine — ranks repos by keyword overlap with work item description."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.workflow_repo_selector_api.store import RepoDescription, RepoSelection


class RepoSelector:
    """Ranks repos by keyword overlap with work item description."""

    def select(
        self,
        repos: list[RepoDescription],
        description: str,
        project_id: str,
    ) -> list[RepoSelection]:
        from lintel.workflow_repo_selector_api.store import RepoSelection

        words = set(description.lower().split())
        candidates = [r for r in repos if not project_id or r.project_id == project_id]
        scored: list[RepoSelection] = []
        for repo in candidates:
            repo_words = (
                set(repo.description.lower().split()) | set(repo.tags) | set(repo.languages)
            )
            overlap = words & repo_words
            score = len(overlap) / max(len(words), 1)
            if score > 0:
                scored.append(
                    RepoSelection(
                        repo_id=repo.repo_id,
                        name=repo.name,
                        score=round(score, 3),
                        reason=f"Matched: {', '.join(sorted(overlap))}",
                    )
                )
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored
