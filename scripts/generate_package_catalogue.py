#!/usr/bin/env python3
"""Generate the package catalogue page for the docs site.

Reads all packages/*/pyproject.toml files and produces docs/site/packages.md
with a table of every workspace package, its description, and dependencies.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "packages"
OUTPUT = ROOT / "docs" / "site" / "packages.md"

# Categorise packages into layers for the catalogue.
CORE_PACKAGES = {"contracts", "domain", "agents", "workflows", "app"}
LIBRARY_PACKAGES = {
    "event-store",
    "event-bus",
    "projections",
    "persistence",
    "sandbox",
    "pii",
    "observability",
    "models",
    "slack",
    "channels",
    "telegram",
    "repos",
    "coordination",
    "infrastructure",
    "memory",
    "api-support",
    "context-injection",
}


def load_packages() -> list[dict[str, str | list[str]]]:
    """Load metadata from all pyproject.toml files."""
    packages = []
    for toml_path in sorted(PACKAGES_DIR.glob("*/pyproject.toml")):
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        proj = data.get("project", {})
        name = proj.get("name", toml_path.parent.name)
        desc = proj.get("description", "")
        raw_deps = proj.get("dependencies", [])
        lintel_deps = sorted(
            dep.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
            for dep in raw_deps
            if dep.strip().startswith("lintel-")
        )
        packages.append(
            {
                "dir": toml_path.parent.name,
                "name": name,
                "description": desc,
                "lintel_deps": lintel_deps,
            }
        )
    return packages


def categorise(
    packages: list[dict[str, str | list[str]]],
) -> tuple[
    list[dict[str, str | list[str]]],
    list[dict[str, str | list[str]]],
    list[dict[str, str | list[str]]],
]:
    """Split packages into core, library, and API groups."""
    core, library, api = [], [], []
    for pkg in packages:
        d = pkg["dir"]
        if d in CORE_PACKAGES:
            core.append(pkg)
        elif d in LIBRARY_PACKAGES:
            library.append(pkg)
        else:
            api.append(pkg)
    return core, library, api


def render_table(packages: list[dict[str, str | list[str]]]) -> str:
    """Render a markdown table for a list of packages."""
    lines = ["| Package | Name | Lintel dependencies |", "|---------|------|---------------------|"]
    for pkg in packages:
        deps = ", ".join(str(d) for d in pkg["lintel_deps"]) if pkg["lintel_deps"] else "—"
        lines.append(f"| `packages/{pkg['dir']}/` | `{pkg['name']}` | {deps} |")
    return "\n".join(lines)


def main() -> None:
    packages = load_packages()
    core, library, api = categorise(packages)

    sections = [
        "# Package Catalogue",
        "",
        f"Lintel is a uv workspace monorepo with **{len(packages)} packages** under `packages/`.",
        "This page is auto-generated from `pyproject.toml` files.",
        "",
        "!!! info \"Regenerate this page\"",
        "    Run `python scripts/generate_package_catalogue.py` to update.",
        "",
        f"## Core packages ({len(core)})",
        "",
        render_table(core),
        "",
        f"## Library packages ({len(library)})",
        "",
        render_table(library),
        "",
        f"## API packages ({len(api)})",
        "",
        render_table(api),
        "",
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(sections))
    print(f"Wrote {OUTPUT} ({len(packages)} packages)")


if __name__ == "__main__":
    main()
