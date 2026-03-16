"""Tests for the shared review lifecycle service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agentforge.models.schemas import ReviewRequest
from agentforge.services.review_service import (
    execute_review,
    get_review_response,
    submit_review,
)


class TestReviewService:
    def test_submit_review_persists_pending_record(self, temp_db):
        request = ReviewRequest(code="print('hello')", filename="hello.py")

        submission = submit_review(request, db_path=temp_db)
        stored = get_review_response(submission.review_id, db_path=temp_db)

        assert submission.status == "pending"
        assert stored is not None
        assert stored["status"] == "pending"

    @patch("agentforge.services.review_service.retrieve_context", return_value="related context")
    @pytest.mark.asyncio
    async def test_execute_review_completes_and_persists_result(self, _retrieve_context, temp_db):
        request = ReviewRequest(code="print('hello')", filename="hello.py", context="user context")
        submission = submit_review(request, db_path=temp_db)

        class FakeResult:
            overall_score = 91

            def model_dump_json(self):
                return '{"overall_score": 91, "summary": "Looks good", "findings": [], "conflicts": [], "agent_reports": []}'

        fake_result = FakeResult()

        with patch("agentforge.services.review_service.run_review", new=AsyncMock(return_value=fake_result)):
            await execute_review(submission.review_id, request, db_path=temp_db)

        stored = get_review_response(submission.review_id, db_path=temp_db)
        assert stored is not None
        assert stored["status"] == "completed"
        assert stored["result"]["overall_score"] == 91

    @pytest.mark.asyncio
    async def test_execute_review_marks_failure(self, temp_db):
        request = ReviewRequest(code="raise", filename="bad.py")
        submission = submit_review(request, db_path=temp_db)

        with patch("agentforge.services.review_service.run_review", new=AsyncMock(side_effect=RuntimeError("boom"))):
            await execute_review(submission.review_id, request, db_path=temp_db)

        stored = get_review_response(submission.review_id, db_path=temp_db)
        assert stored is not None
        assert stored["status"] == "failed"
        assert stored["result"]["error"] == "boom"
