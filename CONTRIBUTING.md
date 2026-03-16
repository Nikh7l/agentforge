# Contributing to AgentForge

Thank you for your interest in contributing to AgentForge! This guide will help you get started.

## Development Setup

### Prerequisites
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package manager)
- Python 3.14+

### Install

```bash
git clone https://github.com/your-username/agentforge.git
cd agentforge
uv venv --python 3.14
uv pip install -e ".[dev]"
cp .env.example .env  # Add your OPENROUTER_API_KEY
```

## Development Workflow

### Running Tests

```bash
uv run pytest tests/ -v
```

### Linting & Formatting

```bash
# Check for lint issues
uv run ruff check .

# Auto-fix lint issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Running the API

```bash
uv run uvicorn agentforge.api.app:app --reload
```

### Running the Dashboard

```bash
uv run streamlit run dashboard/app.py
```

## Project Structure

```
agentforge/
├── agents/      # Review agents (router, security, performance, etc.)
├── api/         # FastAPI backend (routes, middleware, logging)
├── cli/         # Typer CLI with Rich output
├── graph/       # LangGraph workflow orchestration
├── models/      # Pydantic schemas + SQLite database
├── rag/         # ChromaDB indexer + retriever
└── services/    # Business logic (review_service, github_client)
```

## Coding Standards

- **Formatter**: Ruff (120-char line length)
- **Linter**: Ruff with bugbear, bandit, isort, pyupgrade rules
- **Types**: Use type hints everywhere; `from __future__ import annotations` at file top
- **Docstrings**: Google-style, required for all public functions
- **Tests**: Pytest; mock LLM calls, never hit real APIs in CI

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Make your changes with tests
3. Ensure all checks pass: `uv run ruff check . && uv run pytest tests/ -v`
4. Write a clear PR description
5. Submit for review

## Architecture Notes

### Agent System
- All agents extend `BaseReviewAgent` which handles LLM invocation and retry logic
- The Router Agent decides which agents to activate based on code analysis
- Agents run in parallel via `asyncio.gather` inside the LangGraph review node
- The Synthesizer Agent merges all reports, deduplicates findings, and resolves conflicts

### Service Layer
- `review_service.py` centralizes review lifecycle logic used by API, CLI, and webhooks
- `github_client.py` handles GitHub API interactions (diff fetching, comment posting)

### Security
- API key auth via `X-API-Key` header (configurable, disabled when no keys set)
- Rate limiting per client IP (configurable RPM)
- Webhook signature verification (HMAC-SHA256)
- Input payload size validation

## License

MIT
