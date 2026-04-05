"""Onboarding wizard — guided setup flow for new Lintel deployments.

Provides step-by-step onboarding with progress tracking and resume support.
Steps: workspace → slack → repo → project → team → ai_model → compliance → done.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

ONBOARDING_STEPS = [
    "workspace",
    "slack",
    "repo",
    "project",
    "team",
    "ai_model",
    "compliance",
    "done",
]

OPTIONAL_STEPS = {"slack", "team", "compliance"}


class StepStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    skipped = "skipped"


class StepPayload(BaseModel):
    """Payload for completing or skipping an onboarding step."""

    action: Literal["complete", "skip"] = "complete"
    data: dict[str, Any] = {}


def _get_onboarding_state(request: Request) -> dict[str, Any]:
    """Get or initialise onboarding state on app state."""
    if not hasattr(request.app.state, "onboarding"):
        request.app.state.onboarding = {
            "current_step": "workspace",
            "steps": {s: StepStatus.pending.value for s in ONBOARDING_STEPS},
        }
    return request.app.state.onboarding  # type: ignore[no-any-return]


def _advance_current_step(state: dict[str, Any]) -> None:
    """Advance current_step to the next pending step, or 'done'."""
    for step in ONBOARDING_STEPS:
        if state["steps"][step] == StepStatus.pending.value:
            state["current_step"] = step
            return
    state["current_step"] = "done"


async def _validate_workspace(data: dict[str, Any], request: Request) -> None:
    name = data.get("workspace_name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="workspace_name is required")
    settings = _get_general_settings(request)
    settings["workspace_name"] = name
    slug = data.get("workspace_slug", "")
    if slug:
        settings["workspace_slug"] = slug


async def _validate_slack(data: dict[str, Any], request: Request) -> None:
    # Optional step — no strict validation. Slack is connected via the connections API.
    pass


async def _validate_repo(data: dict[str, Any], request: Request) -> None:
    repo_store = request.app.state.repository_store
    repos = await repo_store.list_all()
    mode = data.get("mode", "register")

    if mode == "create":
        # Create a new repo via GitHub API
        repo_provider = getattr(request.app.state, "repo_provider", None)
        if repo_provider is None:
            raise HTTPException(status_code=503, detail="Repository provider not configured")
        name = data.get("name", "").strip()
        owner = data.get("owner", "").strip()
        if not name or not owner:
            raise HTTPException(
                status_code=422,
                detail="'name' and 'owner' are required when mode=create",
            )
        template_str = data.get("template")
        template = None
        if template_str:
            from lintel.repos.types import RepoTemplate

            try:
                template = RepoTemplate(template_str)
            except ValueError:
                raise HTTPException(  # noqa: B904
                    status_code=422,
                    detail=f"Unknown template: {template_str}",
                )
        result = await repo_provider.create_repo(
            owner, name, private=data.get("private", True), template=template
        )
        from lintel.repos.types import Repository

        repo = Repository(
            repo_id=str(__import__("uuid").uuid4()),
            name=result.name,
            url=result.repo_url,
            default_branch=result.default_branch,
            owner=result.owner,
            provider="github",
        )
        await repo_store.add(repo)
        return

    if not repos and not data.get("url"):
        raise HTTPException(
            status_code=422,
            detail="At least one repository is required. "
            "Provide 'url', or use mode=create to create a new repo.",
        )
    if data.get("url"):
        await repo_store.add({"name": data.get("name", "default"), "url": data["url"]})


async def _validate_project(data: dict[str, Any], request: Request) -> None:
    if not data.get("name"):
        raise HTTPException(status_code=422, detail="Project name is required")


async def _validate_ai_model(data: dict[str, Any], request: Request) -> None:
    ai_store = request.app.state.ai_provider_store
    providers = await ai_store.list_all()
    if not providers and not data.get("provider_type"):
        raise HTTPException(
            status_code=422,
            detail="At least one AI provider required. "
            "Provide 'provider_type' or register one first.",
        )


async def _validate_compliance(data: dict[str, Any], request: Request) -> None:
    level = data.get("level", "none")
    if level not in ("none", "soc2", "hipaa"):
        raise HTTPException(status_code=422, detail="level must be one of: none, soc2, hipaa")


_StepValidator = Callable[[dict[str, Any], Request], Awaitable[None]]

_VALIDATORS: dict[str, _StepValidator] = {
    "workspace": _validate_workspace,
    "slack": _validate_slack,
    "repo": _validate_repo,
    "project": _validate_project,
    "ai_model": _validate_ai_model,
    "compliance": _validate_compliance,
}


def _get_general_settings(request: Request) -> dict[str, Any]:
    if not hasattr(request.app.state, "general_settings"):
        from lintel.persistence.data_models import GeneralSettings

        request.app.state.general_settings = GeneralSettings().model_dump()
    return request.app.state.general_settings  # type: ignore[no-any-return]


@router.get("/onboarding/status")
async def get_onboarding_status(request: Request) -> dict[str, Any]:
    """Check which onboarding steps have been completed."""
    ai_provider_store = request.app.state.ai_provider_store
    repo_store = request.app.state.repository_store

    providers = await ai_provider_store.list_all()
    repos = await repo_store.list_all()

    connections: list[dict[str, Any]] = []
    if hasattr(request.app.state, "connections"):
        connections = list(request.app.state.connections.values())

    has_chat = any(c.get("connection_type") == "slack" for c in connections)
    has_ai_provider = len(providers) > 0
    has_repo = len(repos) > 0

    state = _get_onboarding_state(request)
    is_complete = state["current_step"] == "done" or (has_ai_provider and has_repo)

    return {
        "current_step": state["current_step"],
        "steps": state["steps"],
        "has_ai_provider": has_ai_provider,
        "has_repo": has_repo,
        "has_chat": has_chat,
        "is_complete": is_complete,
        "providers_count": len(providers),
        "repos_count": len(repos),
    }


@router.post("/onboarding/steps/{step}")
async def complete_onboarding_step(
    step: str, body: StepPayload, request: Request
) -> dict[str, Any]:
    """Complete or skip an onboarding step."""
    if step not in ONBOARDING_STEPS:
        raise HTTPException(status_code=404, detail=f"Unknown step: {step}")

    if step == "done":
        raise HTTPException(status_code=400, detail="Cannot post to 'done' step")

    state = _get_onboarding_state(request)

    if state["steps"][step] in (StepStatus.completed.value, StepStatus.skipped.value):
        raise HTTPException(status_code=409, detail=f"Step '{step}' already completed")

    if body.action == "skip":
        if step not in OPTIONAL_STEPS:
            raise HTTPException(
                status_code=400, detail=f"Step '{step}' is required and cannot be skipped"
            )
        state["steps"][step] = StepStatus.skipped.value
        _advance_current_step(state)
        return {"step": step, "status": "skipped", "current_step": state["current_step"]}

    # Validate step data
    validator = _VALIDATORS.get(step)
    if validator:
        await validator(body.data, request)

    state["steps"][step] = StepStatus.completed.value

    # Mark done if all non-optional steps are completed
    all_required_done = all(
        state["steps"][s] != StepStatus.pending.value for s in ONBOARDING_STEPS if s != "done"
    )
    if all_required_done:
        state["steps"]["done"] = StepStatus.completed.value
        state["current_step"] = "done"
    else:
        _advance_current_step(state)

    return {
        "step": step,
        "status": "completed",
        "current_step": state["current_step"],
    }
