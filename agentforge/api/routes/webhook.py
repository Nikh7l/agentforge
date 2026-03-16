"""GitHub webhook handler — receives PR events, verifies signatures, and triggers reviews."""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from agentforge.config import GITHUB_WEBHOOK_SECRET
from agentforge.models.schemas import ReviewRequest
from agentforge.services.github_client import fetch_pr_diff, format_review_as_markdown, post_review_comment
from agentforge.services.review_service import execute_review, submit_review

logger = logging.getLogger(__name__)
router = APIRouter()


async def _verify_signature(request: Request) -> None:
    """Verify the GitHub webhook signature (X-Hub-Signature-256).

    Raises HTTPException if the signature is invalid.
    """
    if not GITHUB_WEBHOOK_SECRET:
        return  # Skip verification if no secret configured

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    body = await request.body()
    expected = (
        "sha256="
        + hmac.new(
            GITHUB_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )

    if not hmac.compare_digest(signature_header, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


async def _run_github_review(
    review_id: str,
    request: ReviewRequest,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
) -> None:
    """Background task: run review then post results back to GitHub PR."""
    await execute_review(review_id, request)

    # Post review comment back to GitHub
    from agentforge.services.review_service import get_review_response

    review_data = get_review_response(review_id)
    if review_data and review_data.get("status") == "completed" and review_data.get("result"):
        markdown = format_review_as_markdown(review_data["result"])
        try:
            post_review_comment(owner, repo, pr_number, markdown, head_sha)
        except Exception as e:
            logger.error("Failed to post GitHub review comment: %s", e)


@router.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events for pull requests.

    Verifies the webhook signature, fetches the actual PR diff from GitHub,
    runs a multi-agent review, and posts results back as a PR review comment.
    """
    await _verify_signature(request)

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

    action = payload.get("action")
    pr = payload.get("pull_request")

    if not pr or action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": f"action={action}"}

    # Extract PR info
    owner = payload.get("repository", {}).get("owner", {}).get("login", "")
    repo = payload.get("repository", {}).get("name", "")
    pr_number = pr.get("number", 0)
    pr_title = pr.get("title", "Untitled PR")
    head_sha = pr.get("head", {}).get("sha", "")

    # Fetch the actual diff from GitHub API
    try:
        pr_info = fetch_pr_diff(owner, repo, pr_number)
        code = pr_info.diff
        head_sha = pr_info.head_sha or head_sha
    except Exception as e:
        logger.warning("Failed to fetch PR diff, using PR body: %s", e)
        code = pr.get("body", "") or f"# PR: {pr_title}\n# Could not fetch diff"

    review_request = ReviewRequest(
        code=code,
        filename=f"PR#{pr_number}",
        context=f"Pull Request: {pr_title}",
    )
    submission = submit_review(review_request)

    background_tasks.add_task(
        _run_github_review,
        submission.review_id,
        review_request,
        owner,
        repo,
        pr_number,
        head_sha,
    )

    logger.info("GitHub webhook: created review %s for %s/%s#%d", submission.review_id, owner, repo, pr_number)
    return {"status": "review_started", "review_id": submission.review_id}
