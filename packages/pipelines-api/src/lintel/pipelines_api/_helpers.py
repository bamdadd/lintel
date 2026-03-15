"""Shared helpers used across pipeline route modules."""

from lintel.workflows.types import PipelineRun, Stage


def _stage_names_for_workflow(workflow_definition_id: str) -> tuple[str, ...]:
    """Look up stage names from the seed data for a given workflow."""
    from lintel.domain.seed import DEFAULT_WORKFLOW_DEFINITIONS

    for wf in DEFAULT_WORKFLOW_DEFINITIONS:
        if wf.definition_id == workflow_definition_id:
            return wf.stage_names
    # Fallback for custom workflows
    return (
        "ingest",
        "research",
        "approve_research",
        "plan",
        "approve_spec",
        "implement",
        "review",
        "approved_for_pr",
        "raise_pr",
    )


def _find_stage(run: PipelineRun, stage_id: str) -> Stage | None:
    for s in run.stages:
        if s.stage_id == stage_id:
            return s
    return None
