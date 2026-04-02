"""Feedback tracker — records feedback, computes satisfaction, extracts insights (REQ-F021)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from lintel.domain.feedback.types import (
    ABVariant,
    FeedbackEntry,
    FeedbackType,
    LearningInsight,
)


class FeedbackTracker:
    """In-memory feedback tracker with A/B comparison and insight extraction."""

    def __init__(self) -> None:
        self._entries: list[FeedbackEntry] = []
        self._variants: dict[str, list[ABVariant]] = {}  # experiment_id -> variants

    # -- Feedback recording & querying ------------------------------------

    def record_feedback(self, entry: FeedbackEntry) -> None:
        """Append a feedback entry."""
        self._entries.append(entry)

    def get_feedback(
        self,
        *,
        workflow_run_id: str | None = None,
        stage_id: str | None = None,
        agent_id: str | None = None,
        feedback_type: FeedbackType | None = None,
    ) -> list[FeedbackEntry]:
        """Return feedback entries matching all provided filters."""
        results = self._entries
        if workflow_run_id is not None:
            results = [e for e in results if e.workflow_run_id == workflow_run_id]
        if stage_id is not None:
            results = [e for e in results if e.stage_id == stage_id]
        if agent_id is not None:
            results = [e for e in results if e.agent_id == agent_id]
        if feedback_type is not None:
            results = [e for e in results if e.feedback_type == feedback_type]
        return results

    def compute_satisfaction_rate(self, agent_id: str) -> float:
        """Return the ratio of positive feedback (thumbs_up) to total for an agent.

        Returns 0.0 when there is no feedback.
        """
        agent_entries = [e for e in self._entries if e.agent_id == agent_id]
        if not agent_entries:
            return 0.0
        positive = sum(1 for e in agent_entries if e.feedback_type == FeedbackType.THUMBS_UP)
        return positive / len(agent_entries)

    # -- Insight extraction ------------------------------------------------

    def extract_insights(self, min_frequency: int = 2) -> list[LearningInsight]:
        """Extract recurring patterns from feedback comments.

        Groups feedback by (agent_id, feedback_type) and returns insights
        for combinations that appear at least *min_frequency* times.
        """
        counter: Counter[tuple[str, str]] = Counter()
        for entry in self._entries:
            counter[(entry.agent_id, entry.feedback_type.value)] += 1

        insights: list[LearningInsight] = []
        for (agent_id, fb_type), freq in counter.items():
            if freq >= min_frequency:
                confidence = min(1.0, freq / 10.0)
                insights.append(
                    LearningInsight(
                        pattern=f"{fb_type} on agent {agent_id}",
                        frequency=freq,
                        recommendation=f"Review agent {agent_id} for recurring {fb_type}",
                        confidence=confidence,
                    )
                )
        return insights

    # -- A/B variant management --------------------------------------------

    def register_variant(self, variant: ABVariant) -> None:
        """Register a variant for an experiment."""
        self._variants.setdefault(variant.experiment_id, []).append(variant)

    def record_variant_metrics(
        self, experiment_id: str, variant_id: str, metrics: dict[str, Any]
    ) -> None:
        """Update metrics on an existing variant (replaces the frozen instance)."""
        variants = self._variants.get(experiment_id, [])
        for i, v in enumerate(variants):
            if v.variant_id == variant_id:
                merged = {**v.metrics, **metrics}
                variants[i] = ABVariant(
                    variant_id=v.variant_id,
                    experiment_id=v.experiment_id,
                    name=v.name,
                    config=v.config,
                    metrics={k: float(val) for k, val in merged.items()},
                )
                return

    def compare_variants(self, experiment_id: str) -> ABVariant:
        """Return the winning variant for an experiment (highest satisfaction score).

        Raises ``ValueError`` when the experiment has no registered variants.
        """
        variants = self._variants.get(experiment_id, [])
        if not variants:
            msg = f"No variants registered for experiment {experiment_id}"
            raise ValueError(msg)
        return max(variants, key=lambda v: v.metrics.get("satisfaction", 0.0))
