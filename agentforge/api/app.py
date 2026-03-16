"""FastAPI application factory and lifespan handler."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentforge.api.logging_config import RequestLoggingMiddleware, configure_logging
from agentforge.api.middleware import APIKeyMiddleware, InputValidationMiddleware, RateLimitMiddleware
from agentforge.api.routes import feedback, review, webhook
from agentforge.config import CORS_ORIGINS, LOG_LEVEL
from agentforge.models.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    configure_logging(LOG_LEVEL)
    init_db()
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI app."""
    app = FastAPI(
        title="AgentForge",
        description="Multi-Agent Code Review & Debugging Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost first) ─────────────────────
    # 1. Request logging (outermost — logs everything including rejected)
    app.add_middleware(RequestLoggingMiddleware)

    # 2. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Input validation (reject oversized payloads early)
    app.add_middleware(InputValidationMiddleware)

    # 4. Rate limiting
    app.add_middleware(RateLimitMiddleware)

    # 5. API key auth (innermost — runs just before route handlers)
    app.add_middleware(APIKeyMiddleware)

    # ── Routes ─────────────────────────────────────────────────────────
    app.include_router(review.router, prefix="/api", tags=["reviews"])
    app.include_router(feedback.router, prefix="/api", tags=["feedback"])
    app.include_router(webhook.router, prefix="/api", tags=["webhook"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "agentforge"}

    return app


# Uvicorn entry point
app = create_app()
