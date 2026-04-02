"""Tech stack discovery — analyses project files to detect technologies."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from lintel.domain.techstack.types import TechStackCategory, TechStackEntry, TechStackReport

if TYPE_CHECKING:
    from collections.abc import Callable

# Patterns that this discovery engine can handle.
SUPPORTED_PATTERNS: tuple[str, ...] = (
    "pyproject.toml",
    "package.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
)

# Well-known mappings from package names to categories.
_PYTHON_FRAMEWORKS: frozenset[str] = frozenset(
    {
        "django",
        "flask",
        "fastapi",
        "starlette",
        "tornado",
        "sanic",
        "pyramid",
        "bottle",
        "falcon",
        "litestar",
    }
)

_PYTHON_TOOLS: frozenset[str] = frozenset(
    {
        "ruff",
        "mypy",
        "pytest",
        "black",
        "isort",
        "flake8",
        "pylint",
        "pre-commit",
        "tox",
        "nox",
        "coverage",
    }
)

_PYTHON_DATABASES: frozenset[str] = frozenset(
    {
        "psycopg2",
        "psycopg",
        "asyncpg",
        "sqlalchemy",
        "alembic",
        "redis",
        "pymongo",
        "motor",
    }
)

_JS_FRAMEWORKS: frozenset[str] = frozenset(
    {
        "react",
        "vue",
        "angular",
        "svelte",
        "next",
        "nuxt",
        "express",
        "fastify",
        "nest",
        "remix",
    }
)

_DOCKER_BASE_LANGUAGES: dict[str, str] = {
    "python": "Python",
    "node": "Node.js",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "java": "Java",
    "openjdk": "Java",
    "php": "PHP",
    "elixir": "Elixir",
    "dotnet": ".NET",
}


def _classify_python_package(name: str) -> TechStackCategory:
    canonical = name.lower().replace("-", "").replace("_", "")
    # Check against known sets (normalised)
    if any(canonical == f.replace("-", "").replace("_", "") for f in _PYTHON_FRAMEWORKS):
        return TechStackCategory.FRAMEWORK
    if any(canonical == t.replace("-", "").replace("_", "") for t in _PYTHON_TOOLS):
        return TechStackCategory.TOOL
    if any(canonical == d.replace("-", "").replace("_", "") for d in _PYTHON_DATABASES):
        return TechStackCategory.DATABASE
    return TechStackCategory.LIBRARY


def _classify_js_package(name: str) -> TechStackCategory:
    base = name.lstrip("@").split("/")[-1].lower()
    if base in _JS_FRAMEWORKS:
        return TechStackCategory.FRAMEWORK
    return TechStackCategory.LIBRARY


def _parse_version(raw: str) -> str:
    """Normalise a version string, stripping common prefixes."""
    raw = raw.strip()
    if raw.startswith(("^", "~", ">=", "<=", "==", "!=")):
        raw = re.sub(r"^[^0-9*]+", "", raw)
    return raw or "*"


class TechStackDiscovery:
    """Analyses project files to detect the tech stack."""

    def discover_from_file(
        self,
        filename: str,
        content: str,
    ) -> list[TechStackEntry]:
        """Detect tech stack entries from a single project file.

        Args:
            filename: The basename or relative path of the file.
            content: The full text content of the file.

        Returns:
            A list of discovered TechStackEntry items.
        """
        basename = filename.rsplit("/", maxsplit=1)[-1]

        dispatch: dict[str, Callable[[str, str], list[TechStackEntry]]] = {
            "pyproject.toml": self._parse_pyproject,
            "package.json": self._parse_package_json,
            "Dockerfile": self._parse_dockerfile,
            "docker-compose.yml": self._parse_docker_compose,
            "docker-compose.yaml": self._parse_docker_compose,
            "Makefile": self._parse_makefile,
            "requirements.txt": self._parse_requirements_txt,
            "Cargo.toml": self._parse_cargo_toml,
            "go.mod": self._parse_go_mod,
        }
        parser = dispatch.get(basename)
        if parser is None:
            return []
        return parser(filename, content)

    def discover_report(
        self,
        files: dict[str, str],
    ) -> TechStackReport:
        """Analyse multiple files and return a deduplicated report.

        Args:
            files: Mapping of filename -> content.
        """
        all_entries: list[TechStackEntry] = []
        for fname, content in files.items():
            all_entries.extend(self.discover_from_file(fname, content))
        return TechStackReport.from_entries(all_entries)

    # --- private parsers ---------------------------------------------------

    def _parse_pyproject(self, filename: str, content: str) -> list[TechStackEntry]:
        entries: list[TechStackEntry] = []
        # Detect python version
        m = re.search(r'requires-python\s*=\s*"([^"]+)"', content)
        if m:
            entries.append(
                TechStackEntry(
                    name="Python",
                    version=_parse_version(m.group(1)),
                    category=TechStackCategory.LANGUAGE,
                    source_file=filename,
                    confidence=1.0,
                )
            )

        # Collect dependencies from [project.dependencies] and optional-deps
        for dep_match in re.finditer(
            r'^\s*"([A-Za-z0-9_-]+)(?:\[.*?\])?([><=!~^][^"]*)?"\s*,?\s*$',
            content,
            re.MULTILINE,
        ):
            name = dep_match.group(1)
            version = _parse_version(dep_match.group(2) or "*")
            cat = _classify_python_package(name)
            entries.append(
                TechStackEntry(
                    name=name,
                    version=version,
                    category=cat,
                    source_file=filename,
                    confidence=0.9,
                )
            )
        return entries

    def _parse_package_json(self, filename: str, content: str) -> list[TechStackEntry]:
        entries: list[TechStackEntry] = []
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return entries

        entries.append(
            TechStackEntry(
                name="Node.js",
                version=data.get("engines", {}).get("node", "*"),
                category=TechStackCategory.LANGUAGE,
                source_file=filename,
                confidence=0.9,
            )
        )

        for section in ("dependencies", "devDependencies"):
            deps: dict[str, str] = data.get(section, {})
            for name, ver in deps.items():
                cat = _classify_js_package(name)
                if section == "devDependencies" and cat == TechStackCategory.LIBRARY:
                    cat = TechStackCategory.TOOL
                entries.append(
                    TechStackEntry(
                        name=name,
                        version=_parse_version(ver),
                        category=cat,
                        source_file=filename,
                        confidence=0.9,
                    )
                )
        return entries

    def _parse_dockerfile(self, filename: str, content: str) -> list[TechStackEntry]:
        entries: list[TechStackEntry] = []
        entries.append(
            TechStackEntry(
                name="Docker",
                version="*",
                category=TechStackCategory.INFRASTRUCTURE,
                source_file=filename,
                confidence=1.0,
            )
        )
        for m in re.finditer(r"^FROM\s+(\S+)", content, re.MULTILINE):
            image = m.group(1)
            parts = image.split(":")
            image_name = parts[0].split("/")[-1]
            version = parts[1] if len(parts) > 1 else "*"
            lang = _DOCKER_BASE_LANGUAGES.get(image_name)
            if lang:
                entries.append(
                    TechStackEntry(
                        name=lang,
                        version=_parse_version(version),
                        category=TechStackCategory.LANGUAGE,
                        source_file=filename,
                        confidence=0.8,
                    )
                )
        return entries

    def _parse_docker_compose(self, filename: str, content: str) -> list[TechStackEntry]:
        entries: list[TechStackEntry] = []
        entries.append(
            TechStackEntry(
                name="Docker Compose",
                version="*",
                category=TechStackCategory.INFRASTRUCTURE,
                source_file=filename,
                confidence=1.0,
            )
        )
        # Detect common service images
        for m in re.finditer(r"image:\s*(\S+)", content):
            image = m.group(1).strip("\"'")
            parts = image.split(":")
            image_name = parts[0].split("/")[-1]
            version = parts[1] if len(parts) > 1 else "*"
            service_map: dict[str, tuple[str, TechStackCategory]] = {
                "postgres": ("PostgreSQL", TechStackCategory.DATABASE),
                "redis": ("Redis", TechStackCategory.DATABASE),
                "mongo": ("MongoDB", TechStackCategory.DATABASE),
                "mysql": ("MySQL", TechStackCategory.DATABASE),
                "nats": ("NATS", TechStackCategory.SERVICE),
                "rabbitmq": ("RabbitMQ", TechStackCategory.SERVICE),
                "elasticsearch": ("Elasticsearch", TechStackCategory.SERVICE),
                "nginx": ("Nginx", TechStackCategory.INFRASTRUCTURE),
            }
            mapped = service_map.get(image_name)
            if mapped:
                entries.append(
                    TechStackEntry(
                        name=mapped[0],
                        version=_parse_version(version),
                        category=mapped[1],
                        source_file=filename,
                        confidence=0.9,
                    )
                )
        return entries

    def _parse_makefile(self, filename: str, content: str) -> list[TechStackEntry]:
        entries: list[TechStackEntry] = []
        entries.append(
            TechStackEntry(
                name="Make",
                version="*",
                category=TechStackCategory.TOOL,
                source_file=filename,
                confidence=1.0,
            )
        )
        # Detect tool usage in Makefile
        tool_patterns: dict[str, tuple[str, TechStackCategory]] = {
            r"\buv\b": ("uv", TechStackCategory.TOOL),
            r"\bnpm\b": ("npm", TechStackCategory.TOOL),
            r"\byarn\b": ("yarn", TechStackCategory.TOOL),
            r"\bpnpm\b": ("pnpm", TechStackCategory.TOOL),
            r"\bdocker\b": ("Docker", TechStackCategory.INFRASTRUCTURE),
            r"\bpytest\b": ("pytest", TechStackCategory.TOOL),
            r"\bmypy\b": ("mypy", TechStackCategory.TOOL),
            r"\bruff\b": ("ruff", TechStackCategory.TOOL),
        }
        for pattern, (name, cat) in tool_patterns.items():
            if re.search(pattern, content):
                entries.append(
                    TechStackEntry(
                        name=name,
                        version="*",
                        category=cat,
                        source_file=filename,
                        confidence=0.7,
                    )
                )
        return entries

    def _parse_requirements_txt(self, filename: str, content: str) -> list[TechStackEntry]:
        entries: list[TechStackEntry] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            m = re.match(r"^([A-Za-z0-9_-]+)(?:\[.*?\])?\s*([><=!~]+\s*\S+)?", line)
            if m:
                name = m.group(1)
                version = _parse_version(m.group(2) or "*")
                cat = _classify_python_package(name)
                entries.append(
                    TechStackEntry(
                        name=name,
                        version=version,
                        category=cat,
                        source_file=filename,
                        confidence=0.9,
                    )
                )
        return entries

    def _parse_cargo_toml(self, filename: str, content: str) -> list[TechStackEntry]:
        entries: list[TechStackEntry] = []
        entries.append(
            TechStackEntry(
                name="Rust",
                version="*",
                category=TechStackCategory.LANGUAGE,
                source_file=filename,
                confidence=1.0,
            )
        )
        # Parse [dependencies] section
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if re.match(r"^\[dependencies\]", stripped):
                in_deps = True
                continue
            if stripped.startswith("[") and in_deps:
                in_deps = False
                continue
            if in_deps:
                m = re.match(r'^(\w[\w-]*)\s*=\s*"([^"]*)"', stripped)
                if m:
                    entries.append(
                        TechStackEntry(
                            name=m.group(1),
                            version=m.group(2),
                            category=TechStackCategory.LIBRARY,
                            source_file=filename,
                            confidence=0.9,
                        )
                    )
                # Handle { version = "..." } syntax
                m2 = re.match(r'^(\w[\w-]*)\s*=\s*\{.*?version\s*=\s*"([^"]*)"', stripped)
                if m2:
                    entries.append(
                        TechStackEntry(
                            name=m2.group(1),
                            version=m2.group(2),
                            category=TechStackCategory.LIBRARY,
                            source_file=filename,
                            confidence=0.9,
                        )
                    )
        return entries

    def _parse_go_mod(self, filename: str, content: str) -> list[TechStackEntry]:
        entries: list[TechStackEntry] = []
        # Go version
        m = re.search(r"^go\s+(\S+)", content, re.MULTILINE)
        if m:
            entries.append(
                TechStackEntry(
                    name="Go",
                    version=m.group(1),
                    category=TechStackCategory.LANGUAGE,
                    source_file=filename,
                    confidence=1.0,
                )
            )
        # Require block
        for m in re.finditer(r"^\s+(\S+)\s+(v\S+)", content, re.MULTILINE):
            module_path = m.group(1)
            version = m.group(2)
            # Use last path segment as name
            name = module_path.rsplit("/", maxsplit=1)[-1]
            entries.append(
                TechStackEntry(
                    name=name,
                    version=version,
                    category=TechStackCategory.LIBRARY,
                    source_file=filename,
                    confidence=0.9,
                )
            )
        return entries
