"""Migration 004: Seed default agents, skills, and workflow definitions.

This migration uses the domain types from contracts.types via the seed module
so that schema refactors are caught by the type checker. The actual SQL
inserts into the generic ``entities`` table (migration 003).

Run with: uv run python migrations/004_seed_agents_skills_workflows.py
Or import generate_sql() to get the raw SQL statements.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from typing import Any


def _serialize(obj: object) -> dict[str, Any]:
    """Serialize a frozen dataclass to a JSON-safe dict."""
    data = dataclasses.asdict(obj)  # type: ignore[arg-type]
    for key, value in data.items():
        if isinstance(value, (frozenset, tuple)):
            data[key] = list(value)
    return data


def _escape_sql_string(s: str) -> str:
    """Escape single quotes for SQL string literals."""
    return s.replace("'", "''")


def _insert_sql(kind: str, entity_id: str, data: dict[str, Any]) -> str:
    """Generate an upsert SQL statement."""
    json_str = _escape_sql_string(json.dumps(data, default=str))
    eid = _escape_sql_string(entity_id)
    return (
        f"INSERT INTO entities (kind, entity_id, data) "
        f"VALUES ('{kind}', '{eid}', '{json_str}'::jsonb) "
        f"ON CONFLICT (kind, entity_id) DO UPDATE SET data = EXCLUDED.data, updated_at = now();"
    )


def generate_sql() -> str:
    """Generate all seed SQL from the domain types."""
    from lintel.api.domain.seed import (
        DEFAULT_AGENTS,
        DEFAULT_SKILLS,
        DEFAULT_WORKFLOW_DEFINITIONS,
    )

    lines: list[str] = [
        "-- Migration 004: Seed default agents, skills, and workflow definitions",
        "-- Auto-generated from lintel.domain.seed using domain types",
        "-- Re-run this migration to update built-in definitions",
        "",
        "BEGIN;",
        "",
        "-- Agents",
    ]

    for agent in DEFAULT_AGENTS:
        data = _serialize(agent)
        lines.append(_insert_sql("agent_definition", agent.agent_id, data))

    lines.append("")
    lines.append("-- Skills")
    for skill in DEFAULT_SKILLS:
        data = _serialize(skill)
        lines.append(_insert_sql("skill", skill.skill_id, data))

    lines.append("")
    lines.append("-- Workflow definitions")
    for wf in DEFAULT_WORKFLOW_DEFINITIONS:
        data = _serialize(wf)
        lines.append(_insert_sql("workflow_definition", wf.definition_id, data))

    lines.append("")
    lines.append("COMMIT;")
    return "\n".join(lines)


def generate_sql_file() -> None:
    """Write the generated SQL to a .sql file next to this script."""
    from pathlib import Path

    sql = generate_sql()
    out = Path(__file__).with_suffix(".sql")
    out.write_text(sql + "\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    if "--file" in sys.argv:
        generate_sql_file()
    else:
        print(generate_sql())
