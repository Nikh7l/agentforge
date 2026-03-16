"""Security middleware — API key auth, rate limiting, and input validation."""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agentforge.config import API_KEYS, MAX_CODE_SIZE, RATE_LIMIT_RPM

logger = logging.getLogger(__name__)

# ── Paths that don't require authentication ────────────────────────────
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


# ── API Key Authentication ─────────────────────────────────────────────


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate API key from X-API-Key header.

    If no API keys are configured (empty set), auth is disabled — useful
    for local development.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth if no keys configured or path is public
        if not API_KEYS or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip for preflight OPTIONS
        if request.method == "OPTIONS":
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        # Compare hashes to avoid timing attacks
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        valid_hashes = {hashlib.sha256(k.encode()).hexdigest() for k in API_KEYS}

        if key_hash not in valid_hashes:
            logger.warning("Unauthorized request from %s to %s", request.client.host, request.url.path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Provide X-API-Key header."},
            )

        return await call_next(request)


# ── Rate Limiting ──────────────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter per client IP.

    Limits requests to RATE_LIMIT_RPM per minute. Set to 0 to disable.
    """

    def __init__(self, app: FastAPI) -> None:
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if RATE_LIMIT_RPM <= 0 or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60.0  # 1 minute

        # Clean old entries
        self._requests[client_ip] = [t for t in self._requests[client_ip] if now - t < window]

        if len(self._requests[client_ip]) >= RATE_LIMIT_RPM:
            retry_after = int(window - (now - self._requests[client_ip][0])) + 1
            logger.warning("Rate limit exceeded for %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Try again in {retry_after}s."},
                headers={"Retry-After": str(retry_after)},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)


# ── Input Validation ───────────────────────────────────────────────────


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Reject oversized payloads before they reach route handlers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_CODE_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Payload too large. Maximum size is {MAX_CODE_SIZE // 1024}KB."},
                )

        return await call_next(request)
