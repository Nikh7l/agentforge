"""Review API routes — submit code, check status, list reviews."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from agentforge.models.schemas import ReviewRequest
from agentforge.services.review_service import (
    execute_review,
    get_review_response,
    list_review_responses,
    submit_review,
)

router = APIRouter()


class ReviewResponse(BaseModel):
    review_id: str
    status: str
    message: str


# ── Endpoints ──────────────────────────────────────────────────────────


@router.post("/review", response_model=ReviewResponse)
async def submit_review_endpoint(body: ReviewRequest, background_tasks: BackgroundTasks):
    """Submit code for review. Returns a review ID immediately."""
    submission = submit_review(body)

    background_tasks.add_task(
        execute_review,
        submission.review_id,
        body,
    )

    return ReviewResponse(
        review_id=submission.review_id,
        status=submission.status,
        message=submission.message,
    )


@router.get("/review/{review_id}")
async def get_review_result(review_id: str):
    """Get the result of a review by ID."""
    response = get_review_response(review_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Review not found")

    return response


@router.get("/reviews")
async def list_all_reviews(limit: int = 50):
    """List recent reviews."""
    return list_review_responses(limit)
