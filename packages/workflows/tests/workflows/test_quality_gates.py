"""Tests for quality gate validation functions."""

from __future__ import annotations

from lintel.workflows.nodes._quality_gates import validate_plan, validate_research_report


class TestValidateResearchReport:
    def test_valid_report(self) -> None:
        content = (
            "# Research Report\n\n"
            "## Relevant Files\n"
            "- src/api/routes.py — API route definitions\n"
            "- src/models/user.py — User model\n"
            "- src/services/auth.py — Authentication service\n"
            "- tests/test_routes.py — Route tests\n\n"
            "## Current Architecture\n"
            "The system uses a layered architecture with routes calling services.\n\n"
            "## Key Patterns\n"
            "All routes use dependency injection via FastAPI Depends.\n\n"
            "## Impact Analysis\n"
            "Changes to auth.py will affect routes.py and test_routes.py.\n\n"
            "## Recommendations\n"
            "Start by updating the auth service, then update routes.\n"
        )
        errors = validate_research_report(content)
        assert errors == []

    def test_too_short(self) -> None:
        content = "## Relevant Files\n## Current Architecture\n## Key Patterns\n## Impact Analysis\n## Recommendations\n"
        errors = validate_research_report(content)
        assert any("too short" in e.lower() for e in errors)

    def test_missing_sections(self) -> None:
        content = "x" * 600 + "\n## Relevant Files\nfoo.py bar.py baz.py\n"
        errors = validate_research_report(content)
        missing = [e for e in errors if "Missing section" in e]
        assert len(missing) == 4  # Missing 4 of 5 sections

    def test_too_few_file_refs(self) -> None:
        content = (
            "x" * 600 + "\n"
            "## Relevant Files\n## Current Architecture\n"
            "## Key Patterns\n## Impact Analysis\n## Recommendations\n"
        )
        errors = validate_research_report(content)
        assert any("file path references" in e.lower() for e in errors)

    def test_narration_output_warns(self) -> None:
        """LLM narration like 'Let me read...' produces missing section warnings."""
        content = (
            "Let me read the codebase now. I'll start by examining the main files. "
            "Now I'll look at the tests directory. " * 20
        )
        errors = validate_research_report(content)
        assert len(errors) > 0


class TestValidatePlan:
    def test_valid_plan(self) -> None:
        plan = {
            "tasks": [
                {
                    "title": "Update auth service",
                    "description": "Add OAuth2 support",
                    "file_paths": ["src/auth.py"],
                    "complexity": "M",
                },
                {
                    "title": "Add tests",
                    "description": "Test OAuth2 flow",
                    "file_paths": ["tests/test_auth.py"],
                    "complexity": "S",
                },
            ],
            "summary": "Add OAuth2 support to auth service",
        }
        errors = validate_plan(plan)
        assert errors == []

    def test_single_task_rejected(self) -> None:
        plan = {
            "tasks": [{"title": "Do everything", "description": "All of it", "file_paths": ["x.py"]}],
            "summary": "Do it",
        }
        errors = validate_plan(plan)
        assert any("at least 2 tasks" in e for e in errors)

    def test_empty_tasks(self) -> None:
        plan = {"tasks": [], "summary": "Nothing"}
        errors = validate_plan(plan)
        assert any("at least 2 tasks" in e for e in errors)

    def test_missing_file_paths(self) -> None:
        plan = {
            "tasks": [
                {"title": "A", "description": "Do A", "file_paths": ["a.py"]},
                {"title": "B", "description": "Do B"},  # Missing file_paths
            ],
            "summary": "A and B",
        }
        errors = validate_plan(plan)
        assert any("file_paths" in e for e in errors)

    def test_missing_title(self) -> None:
        plan = {
            "tasks": [
                {"description": "Do A", "file_paths": ["a.py"]},
                {"title": "B", "description": "Do B", "file_paths": ["b.py"]},
            ],
            "summary": "A and B",
        }
        errors = validate_plan(plan)
        assert any("title" in e for e in errors)

    def test_missing_summary(self) -> None:
        plan = {
            "tasks": [
                {"title": "A", "description": "Do A", "file_paths": ["a.py"]},
                {"title": "B", "description": "Do B", "file_paths": ["b.py"]},
            ],
        }
        errors = validate_plan(plan)
        assert any("summary" in e for e in errors)

    def test_no_tasks_key(self) -> None:
        plan = {"summary": "Nothing"}  # type: ignore[dict-item]
        errors = validate_plan(plan)
        assert any("at least 2 tasks" in e for e in errors)
