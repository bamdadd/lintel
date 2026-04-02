"""Repository auto-classifier — maps user messages to relevant repos."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.repos.types import RepoClassification, Repository


@dataclass
class _CacheEntry:
    result: list[RepoClassification]
    expires_at: float


class RepoClassifier:
    """Classifies user messages to the most relevant repository.

    Uses keyword scoring based on repo name, owner, and URL components.
    Returns ranked results with confidence scores.
    """

    def __init__(self, cache_ttl_seconds: float = 300.0) -> None:
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_ttl = cache_ttl_seconds

    def classify(
        self,
        message: str,
        repositories: list[Repository],
    ) -> list[RepoClassification]:
        """Classify a message against available repositories.

        Returns a list of RepoClassification sorted by confidence (descending).
        Only includes repos with confidence > 0.
        """
        cache_key = self._cache_key(message, repositories)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        results = self._score_repos(message, repositories)
        self._set_cached(cache_key, results)
        return results

    def _score_repos(
        self,
        message: str,
        repositories: list[Repository],
    ) -> list[RepoClassification]:
        from lintel.repos.types import RepoClassification

        msg_lower = message.lower()
        msg_tokens = set(re.findall(r"[a-z0-9]+", msg_lower))

        scored: list[RepoClassification] = []
        for repo in repositories:
            score, keywords, reason = self._score_single(msg_lower, msg_tokens, repo)
            if score > 0:
                scored.append(
                    RepoClassification(
                        repo_id=repo.repo_id,
                        repo_name=repo.name,
                        confidence=min(score, 1.0),
                        matched_keywords=tuple(keywords),
                        reason=reason,
                    )
                )

        scored.sort(key=lambda r: r.confidence, reverse=True)
        return scored

    def _score_single(
        self,
        msg_lower: str,
        msg_tokens: set[str],
        repo: Repository,
    ) -> tuple[float, list[str], str]:
        score = 0.0
        keywords: list[str] = []
        reasons: list[str] = []

        # Exact repo name match in message (strongest signal)
        name_lower = repo.name.lower()
        if name_lower in msg_lower:
            score += 0.6
            keywords.append(repo.name)
            reasons.append(f"repo name '{repo.name}' found in message")

        # Name tokens (partial matches)
        name_tokens = set(re.findall(r"[a-z0-9]+", name_lower))
        overlap = msg_tokens & name_tokens
        if overlap and name_lower not in msg_lower:
            token_score = len(overlap) / max(len(name_tokens), 1) * 0.3
            score += token_score
            keywords.extend(sorted(overlap))
            reasons.append(f"name tokens matched: {sorted(overlap)}")

        # Owner match
        if repo.owner:
            owner_lower = repo.owner.lower()
            if owner_lower in msg_lower:
                score += 0.2
                keywords.append(repo.owner)
                reasons.append(f"owner '{repo.owner}' found in message")

        # URL components (org/repo from URL)
        url_parts = _extract_url_parts(repo.url)
        for part in url_parts:
            if part.lower() in msg_lower and part.lower() not in {k.lower() for k in keywords}:
                score += 0.15
                keywords.append(part)
                reasons.append(f"URL component '{part}' found in message")

        return score, keywords, "; ".join(reasons)

    def _cache_key(
        self,
        message: str,
        repositories: list[Repository],
    ) -> str:
        repo_ids = ",".join(sorted(r.repo_id for r in repositories))
        return f"{message.strip().lower()}::{repo_ids}"

    def _get_cached(self, key: str) -> list[RepoClassification] | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            return None
        return entry.result

    def _set_cached(self, key: str, result: list[RepoClassification]) -> None:
        self._cache[key] = _CacheEntry(
            result=result,
            expires_at=time.monotonic() + self._cache_ttl,
        )

    def clear_cache(self) -> None:
        """Clear all cached classification results."""
        self._cache.clear()


def _extract_url_parts(url: str) -> list[str]:
    """Extract meaningful parts from a git URL (org, repo name)."""
    cleaned = url.rstrip("/").removesuffix(".git")
    parts: list[str] = []
    if "/" in cleaned:
        segments = cleaned.split("/")
        for seg in segments[-2:]:
            seg = seg.strip()
            if seg and seg not in ("github.com", "gitlab.com", "https:", "http:", ""):
                parts.append(seg)
    return parts
