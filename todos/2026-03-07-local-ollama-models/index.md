# Todo: local-ollama-models

## Description

Add support for local Ollama models as an LLM provider in Lintel, enabling users to run AI agent workflows against locally-hosted models via Ollama.

## Work Artifacts

| Agent        | File     | Purpose                 |
| ------------ | -------- | ----------------------- |
| task-manager | index.md | Task index and tracking |
| implementation | src/lintel/config.py | Added ollama_api_base setting |
| implementation | src/lintel/infrastructure/models/router.py | Pass api_base to litellm for Ollama |
| implementation | .env.example | Model provider config examples |
| implementation | tests/unit/infrastructure/test_model_router.py | Ollama api_base tests |
| implementation | docs/local-dev.md | Ollama setup docs |

## Notes

Use a new git worktree for implementation.
