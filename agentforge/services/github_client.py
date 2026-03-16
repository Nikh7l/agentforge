"""GitHub API client — fetch PR diffs and post review comments."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from agentforge.config import GITHUB_TOKEN

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


@dataclass(slots=True)
class PRInfo:
    """Parsed pull request metadata."""

    owner: str
    repo: str
    number: int
    title: str
    diff: str
    head_sha: str


def _headers() -> dict[str, str]:
    """Build GitHub API request headers."""
    h = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def fetch_pr_diff(owner: str, repo: str, pr_number: int) -> PRInfo:
    """Fetch the full diff for a pull request.

    Uses the GitHub API to get PR metadata and the patch/diff content.
    """
    with httpx.Client(timeout=30) as client:
        # Get PR metadata
        pr_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
        pr_resp = client.get(pr_url, headers=_headers())
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()

        # Fetch the actual diff
        diff_resp = client.get(
            pr_url,
            headers={**_headers(), "Accept": "application/vnd.github.v3.diff"},
        )
        diff_resp.raise_for_status()

        return PRInfo(
            owner=owner,
            repo=repo,
            number=pr_number,
            title=pr_data.get("title", ""),
            diff=diff_resp.text,
            head_sha=pr_data.get("head", {}).get("sha", ""),
        )


def post_review_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    commit_sha: str,
    event: str = "COMMENT",
) -> dict:
    """Post a review comment on a pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        body: The review body (markdown).
        commit_sha: The commit SHA to attach the review to.
        event: One of APPROVE, REQUEST_CHANGES, COMMENT.
    """
    if not GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set — cannot post review comment")
        return {"status": "skipped", "reason": "no token"}

    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    payload = {
        "commit_id": commit_sha,
        "body": body,
        "event": event,
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
        result = resp.json()
        logger.info("Posted review comment on %s/%s#%d (review_id=%s)", owner, repo, pr_number, result.get("id"))
        return result


def format_review_as_markdown(review: dict) -> str:
    """Convert a SynthesizedReview dict into a GitHub-flavored markdown comment."""
    score = review.get("overall_score", "?")
    summary = review.get("summary", "")
    findings = review.get("findings", [])

    parts = [
        f"## 🔥 AgentForge Code Review — Score: {score}/100\n",
        f"{summary}\n",
    ]

    if findings:
        parts.append("### Findings\n")
        parts.append("| Severity | Category | Description | Fix |")
        parts.append("|----------|----------|-------------|-----|")
        for f in findings:
            sev = f.get("severity", "info")
            emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(sev, "⚪")
            cat = f.get("category", "")
            desc = f.get("description", "").replace("\n", " ")
            fix = f.get("suggested_fix", "—").replace("\n", " ")
            parts.append(f"| {emoji} {sev} | {cat} | {desc} | {fix} |")
    else:
        parts.append("✅ **No issues found — code looks great!**")

    conflicts = review.get("conflicts", [])
    if conflicts:
        parts.append("\n### ⚔️ Resolved Conflicts\n")
        for c in conflicts:
            agents = ", ".join(c.get("agents_involved", []))
            parts.append(f"- **{agents}**: {c.get('description', '')} → {c.get('resolution', '')}")

    parts.append("\n---\n*Reviewed by [AgentForge](https://github.com) — Multi-Agent Code Review Platform*")
    return "\n".join(parts)
