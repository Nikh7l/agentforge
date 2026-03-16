# 🔥 AgentForge

**Multi-Agent Code Review & Debugging Platform**

AgentForge is a production-grade platform where multiple specialized AI agents collaborate to autonomously review, debug, and refactor code. Agents reason about **security**, **performance**, **architecture**, and **correctness**, then a synthesizer meta-agent resolves conflicts and produces a unified review.

## Architecture

```
Code Input (CLI / API / GitHub Webhook)
        │
   ┌────▼─────┐
   │  Router   │  Classifies code → selects agents
   │  Agent    │
   └────┬──────┘
        │ fans out (parallel)
   ┌────┼──────────────┬───────────────┐
   ▼    ▼              ▼               ▼
┌──────┐ ┌───────────┐ ┌────────────┐ ┌──────────┐
│Secury│ │Performance│ │Architecture│ │Correctnss│
│Agent │ │Agent      │ │Agent       │ │Agent     │
└───┬──┘ └─────┬─────┘ └─────┬──────┘ └─────┬────┘
    └──────────┼──────────────┘──────────────┘
          ┌────▼──────┐
          │Synthesizer│  Deduplicates, resolves conflicts, scores
          │  Agent    │
          └────┬──────┘
               ▼
          ┌────┴──────┐
          │ Auto-Fix  │  Generates suggested code patches
          │  Agent    │
          └────┬──────┘
               ▼
      Unified Review (Score + Findings + Fix Suggestions)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Orchestration | LangGraph |
| LLM | OpenRouter (any model — Gemini, Claude, GPT) |
| Vector Database | ChromaDB |
| Backend API | FastAPI |
| CLI | Typer + Rich |
| Dashboard | Streamlit |
| Database | SQLite |
| Package Manager | uv |

## Quick Start

> **Prerequisites**: Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.14+
>
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> uv python install 3.14
> ```

### 1. Install

```bash
cd agentforge
uv venv --python 3.14
uv pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### 3. Use the CLI

```bash
# Review a file
uv run python -m agentforge.cli.main review samples/vulnerable_app.py

# Index a codebase for context-aware reviews
uv run python -m agentforge.cli.main index /path/to/project

# View history
uv run python -m agentforge.cli.main history
```

### 4. Use the API

```bash
# Start the API server
uv run uvicorn agentforge.api.app:app --reload

# Submit a review
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{"code": "import pickle\npickle.loads(user_input)", "filename": "app.py"}'

# Check results
curl http://localhost:8000/api/review/{review_id}
```

### 5. Use the Dashboard

```bash
# Start the API first (in one terminal)
uv run uvicorn agentforge.api.app:app --reload

# Start the dashboard (in another terminal)
uv run streamlit run dashboard/app.py
```

## Agents

| Agent | Focus Area |
|-------|-----------|
| **Router** | Classifies code by language, domain, complexity, and risk |
| **Security** | Injection attacks, auth flaws, secret exposure, insecure deserialization |
| **Performance** | Time/space complexity, N+1 queries, caching, resource leaks |
| **Architecture** | SOLID principles, design patterns, coupling/cohesion, API design |
| **Correctness** | Logic errors, edge cases, null handling, error handling, type issues |
| **Synthesizer** | Deduplicates findings, resolves inter-agent conflicts, scores code 0-100 |
| **Auto-Fix** | Generates suggested code patches with `# FIX:` comments for all findings |

## Feedback Loop

AgentForge tracks whether users **accept** or **reject** each finding. This data is stored in SQLite and surfaced through the analytics dashboard, enabling iterative prompt refinement to improve agent accuracy over time.

## Project Structure

```
agentforge/
├── agentforge/
│   ├── agents/          # 7 agents (router, security, performance, autofix, etc.)
│   ├── api/             # FastAPI backend with review, feedback, webhook routes
│   ├── cli/             # Typer CLI with rich terminal output
│   ├── graph/           # LangGraph workflow orchestration
│   ├── models/          # Pydantic schemas + SQLite database
│   ├── rag/             # ChromaDB + import-aware context resolver
│   └── services/        # Review service + GitHub client
├── dashboard/           # Streamlit dashboard
├── samples/             # Sample code for testing
└── tests/               # 53 Pytest tests
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_database.py -v
```

## License

MIT
