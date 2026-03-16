"""Integration tests for the review service with mocked LLM."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentforge.models.database import get_review
from agentforge.models.schemas import ReviewRequest
from agentforge.services.review_service import execute_review, submit_review

MOCK_AGENT_REPORT = {
    "agent_name": "security",
    "findings": [
        {
            "severity": "critical",
            "category": "SQL Injection",
            "description": "User input directly in SQL query",
            "line_start": 5,
            "line_end": 7,
            "suggested_fix": "Use parameterized queries",
        }
    ],
    "summary": "Found 1 critical issue",
}

MOCK_SYNTHESIZED = MagicMock()
MOCK_SYNTHESIZED.overall_score = 35
MOCK_SYNTHESIZED.model_dump_json.return_value = json.dumps(
    {
        "overall_score": 35,
        "summary": "Critical SQL injection found.",
        "findings": MOCK_AGENT_REPORT["findings"],
        "conflicts": [],
        "agent_reports": [MOCK_AGENT_REPORT],
    }
)


class TestReviewServiceIntegration:
    """Test the service layer end-to-end with mocked LLM calls."""

    def test_submit_creates_pending_review(self, temp_db):
        request = ReviewRequest(code="print('hi')", filename="test.py")
        with patch(
            "agentforge.services.review_service.create_review",
            side_effect=lambda r, **kw: __import__(
                "agentforge.models.database", fromlist=["create_review"]
            ).create_review(r, db_path=temp_db),
        ):
            result = submit_review(request)

        assert result.status == "pending"
        assert result.review_id is not None
        assert len(result.review_id) == 36

    @pytest.mark.asyncio
    async def test_full_review_lifecycle(self, temp_db):
        """Submit → execute → retrieve a review."""
        request = ReviewRequest(
            code="query = f'SELECT * FROM users WHERE id={user_id}'",
            filename="vulnerable.py",
        )

        # Mock the database calls to use temp_db
        with patch(
            "agentforge.services.review_service.create_review",
            side_effect=lambda r, **kw: __import__(
                "agentforge.models.database", fromlist=["create_review"]
            ).create_review(r, db_path=temp_db),
        ):
            with patch(
                "agentforge.services.review_service.start_review",
                side_effect=lambda rid, **kw: __import__(
                    "agentforge.models.database", fromlist=["start_review"]
                ).start_review(rid, db_path=temp_db),
            ):
                with patch(
                    "agentforge.services.review_service.complete_review",
                    side_effect=lambda rid, res, **kw: __import__(
                        "agentforge.models.database", fromlist=["complete_review"]
                    ).complete_review(rid, res, db_path=temp_db),
                ):
                    with patch(
                        "agentforge.services.review_service.fail_review",
                        side_effect=lambda rid, err, **kw: __import__(
                            "agentforge.models.database", fromlist=["fail_review"]
                        ).fail_review(rid, err, db_path=temp_db),
                    ):
                        with patch("agentforge.services.review_service.retrieve_context", return_value=""):
                            with patch(
                                "agentforge.services.review_service.run_review",
                                new_callable=AsyncMock,
                                return_value=MOCK_SYNTHESIZED,
                            ):
                                submission = submit_review(request)
                                await execute_review(submission.review_id, request, db_path=temp_db)

        row = get_review(submission.review_id, db_path=temp_db)
        assert row is not None
        assert row["status"] == "completed"
        result = json.loads(row["result"])
        assert result["overall_score"] == 35
        assert len(result["findings"]) == 1

    @pytest.mark.asyncio
    async def test_review_failure_is_recorded(self, temp_db):
        """Verify that LLM failures result in a 'failed' status."""
        request = ReviewRequest(code="x = 1", filename="simple.py")

        with patch(
            "agentforge.services.review_service.create_review",
            side_effect=lambda r, **kw: __import__(
                "agentforge.models.database", fromlist=["create_review"]
            ).create_review(r, db_path=temp_db),
        ):
            with patch(
                "agentforge.services.review_service.start_review",
                side_effect=lambda rid, **kw: __import__(
                    "agentforge.models.database", fromlist=["start_review"]
                ).start_review(rid, db_path=temp_db),
            ):
                with patch(
                    "agentforge.services.review_service.fail_review",
                    side_effect=lambda rid, err, **kw: __import__(
                        "agentforge.models.database", fromlist=["fail_review"]
                    ).fail_review(rid, err, db_path=temp_db),
                ):
                    with patch("agentforge.services.review_service.retrieve_context", return_value=""):
                        with patch(
                            "agentforge.services.review_service.run_review",
                            new_callable=AsyncMock,
                            side_effect=RuntimeError("LLM API timeout"),
                        ):
                            submission = submit_review(request)
                            await execute_review(submission.review_id, request, db_path=temp_db)

        row = get_review(submission.review_id, db_path=temp_db)
        assert row["status"] == "failed"
