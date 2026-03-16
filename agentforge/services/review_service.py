"""Shared review lifecycle service used by the API, CLI, and webhook flows."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from agentforge.graph.workflow import run_review
from agentforge.models.database import (
    complete_review,
    create_review,
    fail_review,
    get_review,
    list_reviews,
    start_review,
)
from agentforge.models.schemas import ReviewRequest
from agentforge.rag.import_resolver import resolve_import_context
from agentforge.rag.retriever import retrieve_context

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ReviewSubmissionResult:
    """Metadata returned when a review is created."""

    review_id: str
    status: str
    message: str


def submit_review(request: ReviewRequest, db_path: str | None = None) -> ReviewSubmissionResult:
    """Persist a review request and return its initial lifecycle metadata."""
    review_id = create_review(request.model_dump_json(), db_path=db_path)
    return ReviewSubmissionResult(
        review_id=review_id,
        status="pending",
        message="Review submitted. Poll the review endpoint for results.",
    )


async def execute_review(
    review_id: str,
    request: ReviewRequest,
    db_path: str | None = None,
) -> None:
    """Run the review pipeline and persist its outcome."""
    start_review(review_id, db_path=db_path)

    try:
        # Layer 1: Import-aware context (dependency graph)
        import_context = resolve_import_context(request.code, request.filename)

        # Layer 2: RAG similarity search
        rag_context = retrieve_context(request.code)

        # Layer 3: User-provided context
        user_context = request.context or ""

        # Combine all context layers
        context_parts = [p for p in [user_context, import_context, rag_context] if p]
        full_context = "\n\n".join(context_parts)

        result = await run_review(request.code, request.filename, full_context)
        complete_review(review_id, result.model_dump_json(), db_path=db_path)
        logger.info("Review %s completed (score=%s)", review_id, result.overall_score)
    except Exception as exc:
        logger.error("Review %s failed: %s", review_id, exc)
        fail_review(review_id, str(exc), db_path=db_path)


def get_review_response(review_id: str, db_path: str | None = None) -> dict | None:
    """Load a persisted review and normalize it for API/UI consumers."""
    row = get_review(review_id, db_path=db_path)
    if row is None:
        return None

    response = {
        "review_id": row["id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }

    if row["result"]:
        try:
            response["result"] = json.loads(row["result"])
        except json.JSONDecodeError:
            response["result"] = row["result"]

    return response


def list_review_responses(limit: int = 50, db_path: str | None = None) -> list[dict]:
    """Return recent reviews in a transport-friendly shape."""
    return list_reviews(limit=limit, db_path=db_path)
