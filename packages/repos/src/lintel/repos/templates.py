"""Scaffold templates for bootstrapping new repositories.

Each template returns a dict of {filepath: content} representing the initial commit.
"""

from __future__ import annotations

from lintel.repos.types import RepoTemplate

_REACT_VITE_FILES: dict[str, str] = {
    "package.json": """{
  "name": "{{name}}",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }
}
""",
    "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true
  },
  "include": ["src"]
}
""",
    "vite.config.ts": """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
""",
    "index.html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{name}}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""",
    "src/main.tsx": """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
""",
    "src/App.tsx": """function App() {
  return (
    <div>
      <h1>{{name}}</h1>
      <p>Edit src/App.tsx to get started.</p>
    </div>
  )
}

export default App
""",
    ".gitignore": """node_modules/
dist/
*.local
""",
    "README.md": """# {{name}}

React + Vite + TypeScript starter.

```bash
npm install
npm run dev
```
""",
}

_PYTHON_FASTAPI_FILES: dict[str, str] = {
    "pyproject.toml": """[project]
name = "{{name}}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.28"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""",
    "src/__init__.py": "",
    "src/main.py": '''"""{{name}} — FastAPI application."""

from fastapi import FastAPI

app = FastAPI(title="{{name}}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
''',
    "tests/test_health.py": '''"""Health endpoint test."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
''',
    ".gitignore": """__pycache__/
*.py[cod]
.venv/
dist/
*.egg-info/
""",
    "README.md": """# {{name}}

Python + FastAPI starter.

```bash
pip install -e ".[dev]"
uvicorn src.main:app --reload
```
""",
}

_MONOREPO_FILES: dict[str, str] = {
    "pyproject.toml": """[project]
name = "{{name}}"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/*"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""",
    "packages/.gitkeep": "",
    "Makefile": """install:
\tuv sync --all-packages

test:
\tuv run pytest

lint:
\tuv run ruff check .
\tuv run ruff format --check .

format:
\tuv run ruff check --fix .
\tuv run ruff format .
""",
    ".gitignore": """__pycache__/
*.py[cod]
.venv/
dist/
*.egg-info/
node_modules/
""",
    "README.md": """# {{name}}

UV workspace monorepo.

```bash
make install
make test
```
""",
}

_TEMPLATES: dict[RepoTemplate, dict[str, str]] = {
    RepoTemplate.REACT_VITE: _REACT_VITE_FILES,
    RepoTemplate.PYTHON_FASTAPI: _PYTHON_FASTAPI_FILES,
    RepoTemplate.MONOREPO: _MONOREPO_FILES,
}


def get_template_files(template: RepoTemplate, name: str) -> dict[str, str]:
    """Return scaffold files for the given template with name substituted."""
    raw = _TEMPLATES[template]
    return {path: content.replace("{{name}}", name) for path, content in raw.items()}


def list_templates() -> list[str]:
    """Return available template names."""
    return [t.value for t in RepoTemplate]
