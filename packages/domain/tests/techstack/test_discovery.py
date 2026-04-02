"""Tests for TechStackDiscovery."""

from __future__ import annotations

from lintel.domain.techstack.discovery import TechStackDiscovery
from lintel.domain.techstack.types import TechStackCategory


class TestPyprojectToml:
    def setup_method(self) -> None:
        self.disc = TechStackDiscovery()

    def test_detects_python_version(self) -> None:
        content = 'requires-python = ">=3.12"\n'
        entries = self.disc.discover_from_file("pyproject.toml", content)
        python = [e for e in entries if e.name == "Python"]
        assert len(python) == 1
        assert python[0].version == "3.12"
        assert python[0].category == TechStackCategory.LANGUAGE

    def test_detects_dependencies(self) -> None:
        content = """\
[project]
dependencies = [
    "fastapi>=0.100",
    "pydantic>=2.0",
    "ruff>=0.1.0",
]
"""
        entries = self.disc.discover_from_file("pyproject.toml", content)
        names = {e.name for e in entries}
        assert "fastapi" in names
        assert "pydantic" in names
        assert "ruff" in names

    def test_classifies_frameworks(self) -> None:
        content = '    "fastapi>=0.100",\n'
        entries = self.disc.discover_from_file("pyproject.toml", content)
        fastapi = [e for e in entries if e.name == "fastapi"]
        assert fastapi[0].category == TechStackCategory.FRAMEWORK

    def test_classifies_tools(self) -> None:
        content = '    "pytest>=7.0",\n'
        entries = self.disc.discover_from_file("pyproject.toml", content)
        pytest_e = [e for e in entries if e.name == "pytest"]
        assert pytest_e[0].category == TechStackCategory.TOOL

    def test_classifies_databases(self) -> None:
        content = '    "asyncpg>=0.28",\n'
        entries = self.disc.discover_from_file("pyproject.toml", content)
        db = [e for e in entries if e.name == "asyncpg"]
        assert db[0].category == TechStackCategory.DATABASE


class TestPackageJson:
    def setup_method(self) -> None:
        self.disc = TechStackDiscovery()

    def test_detects_node(self) -> None:
        content = '{"engines": {"node": ">=18"}, "dependencies": {}}'
        entries = self.disc.discover_from_file("package.json", content)
        node = [e for e in entries if e.name == "Node.js"]
        assert len(node) == 1
        assert node[0].version == ">=18"

    def test_detects_dependencies(self) -> None:
        content = '{"dependencies": {"react": "^18.2.0", "express": "~4.18.0"}}'
        entries = self.disc.discover_from_file("package.json", content)
        names = {e.name for e in entries}
        assert "react" in names
        assert "express" in names

    def test_classifies_frameworks(self) -> None:
        content = '{"dependencies": {"react": "^18.0"}}'
        entries = self.disc.discover_from_file("package.json", content)
        react = [e for e in entries if e.name == "react"]
        assert react[0].category == TechStackCategory.FRAMEWORK


class TestDockerfile:
    def setup_method(self) -> None:
        self.disc = TechStackDiscovery()

    def test_detects_docker(self) -> None:
        entries = self.disc.discover_from_file("Dockerfile", "FROM python:3.12-slim\n")
        docker = [e for e in entries if e.name == "Docker"]
        assert len(docker) == 1
        assert docker[0].category == TechStackCategory.INFRASTRUCTURE

    def test_detects_base_language(self) -> None:
        entries = self.disc.discover_from_file("Dockerfile", "FROM python:3.12-slim\n")
        python = [e for e in entries if e.name == "Python"]
        assert len(python) == 1
        assert python[0].version == "3.12-slim"


class TestDockerCompose:
    def setup_method(self) -> None:
        self.disc = TechStackDiscovery()

    def test_detects_services(self) -> None:
        content = """\
services:
  db:
    image: postgres:16
  cache:
    image: redis:7.2
"""
        entries = self.disc.discover_from_file("docker-compose.yml", content)
        names = {e.name for e in entries}
        assert "PostgreSQL" in names
        assert "Redis" in names
        assert "Docker Compose" in names


class TestRequirementsTxt:
    def setup_method(self) -> None:
        self.disc = TechStackDiscovery()

    def test_parses_pinned(self) -> None:
        content = "flask==2.3.0\nrequests>=2.28\n"
        entries = self.disc.discover_from_file("requirements.txt", content)
        names = {e.name for e in entries}
        assert "flask" in names
        assert "requests" in names

    def test_skips_comments_and_flags(self) -> None:
        content = "# comment\n-r base.txt\nflask==2.3.0\n"
        entries = self.disc.discover_from_file("requirements.txt", content)
        assert len(entries) == 1


class TestCargoToml:
    def setup_method(self) -> None:
        self.disc = TechStackDiscovery()

    def test_detects_rust(self) -> None:
        content = '[package]\nname = "myapp"\n\n[dependencies]\nserde = "1.0"\n'
        entries = self.disc.discover_from_file("Cargo.toml", content)
        rust = [e for e in entries if e.name == "Rust"]
        assert len(rust) == 1
        serde = [e for e in entries if e.name == "serde"]
        assert len(serde) == 1
        assert serde[0].version == "1.0"


class TestGoMod:
    def setup_method(self) -> None:
        self.disc = TechStackDiscovery()

    def test_detects_go(self) -> None:
        content = (
            "module example.com/app\n\ngo 1.22\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n)\n"
        )
        entries = self.disc.discover_from_file("go.mod", content)
        go = [e for e in entries if e.name == "Go"]
        assert len(go) == 1
        assert go[0].version == "1.22"
        gin = [e for e in entries if e.name == "gin"]
        assert len(gin) == 1


class TestMakefile:
    def setup_method(self) -> None:
        self.disc = TechStackDiscovery()

    def test_detects_tools(self) -> None:
        content = "test:\n\tuv run pytest\n\ncheck:\n\tuv run ruff check\n"
        entries = self.disc.discover_from_file("Makefile", content)
        names = {e.name for e in entries}
        assert "Make" in names
        assert "uv" in names
        assert "pytest" in names
        assert "ruff" in names


class TestUnsupportedFile:
    def test_returns_empty(self) -> None:
        disc = TechStackDiscovery()
        assert disc.discover_from_file("README.md", "# Hello") == []


class TestDiscoverReport:
    def test_multi_file_report(self) -> None:
        disc = TechStackDiscovery()
        files = {
            "pyproject.toml": 'requires-python = ">=3.12"\n',
            "Dockerfile": "FROM python:3.12-slim\n",
        }
        report = disc.discover_report(files)
        python = [e for e in report.entries if e.name == "Python"]
        # Deduplication: only one Python entry (highest confidence)
        assert len(python) == 1
        assert python[0].confidence == 1.0
        assert len(report.source_files) == 2
