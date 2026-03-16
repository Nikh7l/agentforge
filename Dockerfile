# ── Build stage ─────────────────────────────────────────────────────────
FROM python:3.14-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Create venv and install dependencies
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e "."

# ── Runtime stage ──────────────────────────────────────────────────────
FROM python:3.14-slim AS runtime

WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY agentforge/ ./agentforge/
COPY dashboard/ ./dashboard/
COPY samples/ ./samples/
COPY pyproject.toml ./

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8000

# Default: run the API server
CMD ["uvicorn", "agentforge.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
