"""Feedback API routes — accept/reject findings and view stats."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agentforge.models.database import (
    get_feedback_stats,
    get_review,
    save_feedback,
)

router = APIRouter()


class FeedbackBody(BaseModel):
    finding_id: str
    accepted: bool
    comment: str | None = None


@router.post("/review/{review_id}/feedback")
async def submit_feedback(review_id: str, body: FeedbackBody):
    """Submit feedback on a specific finding within a review."""
    row = get_review(review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Review not found")

    feedback_id = save_feedback(
        review_id=review_id,
        finding_id=body.finding_id,
        accepted=body.accepted,
        comment=body.comment,
    )

    return {"feedback_id": feedback_id, "status": "saved"}


@router.get("/feedback/stats")
async def feedback_stats():
    """Get aggregate feedback statistics."""
    return get_feedback_stats()
