"""Tests for scaffold template generation."""

from __future__ import annotations

from lintel.repos.templates import get_template_files, list_templates
from lintel.repos.types import RepoTemplate


class TestListTemplates:
    def test_returns_all_template_names(self) -> None:
        templates = list_templates()
        assert "react-vite" in templates
        assert "python-fastapi" in templates
        assert "monorepo" in templates
        assert len(templates) == 3


class TestGetTemplateFiles:
    def test_react_vite_has_expected_files(self) -> None:
        files = get_template_files(RepoTemplate.REACT_VITE, "my-app")
        assert "package.json" in files
        assert "src/App.tsx" in files
        assert "vite.config.ts" in files
        assert "index.html" in files
        assert ".gitignore" in files

    def test_python_fastapi_has_expected_files(self) -> None:
        files = get_template_files(RepoTemplate.PYTHON_FASTAPI, "my-api")
        assert "pyproject.toml" in files
        assert "src/main.py" in files
        assert "tests/test_health.py" in files
        assert ".gitignore" in files

    def test_monorepo_has_expected_files(self) -> None:
        files = get_template_files(RepoTemplate.MONOREPO, "my-mono")
        assert "pyproject.toml" in files
        assert "Makefile" in files
        assert "packages/.gitkeep" in files

    def test_name_substitution(self) -> None:
        files = get_template_files(RepoTemplate.REACT_VITE, "cool-project")
        assert "cool-project" in files["package.json"]
        assert "cool-project" in files["README.md"]
        assert "cool-project" in files["index.html"]

    def test_python_name_substitution(self) -> None:
        files = get_template_files(RepoTemplate.PYTHON_FASTAPI, "my-service")
        assert "my-service" in files["pyproject.toml"]
        assert "my-service" in files["src/main.py"]
