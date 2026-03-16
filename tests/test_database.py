"""Tests for the database layer."""

from __future__ import annotations

import json

from agentforge.models.database import (
    complete_review,
    create_review,
    fail_review,
    get_feedback_stats,
    get_review,
    list_reviews,
    save_feedback,
    start_review,
)


class TestDatabase:
    """Test SQLite CRUD operations."""

    def test_create_and_get_review(self, temp_db):
        request = json.dumps({"code": "print('hello')", "filename": "test.py"})
        review_id = create_review(request, db_path=temp_db)

        assert review_id is not None
        assert len(review_id) == 36  # UUID format

        row = get_review(review_id, db_path=temp_db)
        assert row is not None
        assert row["status"] == "pending"
        assert row["request"] == request

    def test_complete_review(self, temp_db):
        request = json.dumps({"code": "x = 1"})
        review_id = create_review(request, db_path=temp_db)
        start_review(review_id, db_path=temp_db)

        result = json.dumps({"overall_score": 85, "summary": "Good code"})
        complete_review(review_id, result, db_path=temp_db)

        row = get_review(review_id, db_path=temp_db)
        assert row["status"] == "completed"
        assert row["completed_at"] is not None
        assert json.loads(row["result"])["overall_score"] == 85

    def test_start_review(self, temp_db):
        review_id = create_review("{}", db_path=temp_db)
        start_review(review_id, db_path=temp_db)

        row = get_review(review_id, db_path=temp_db)
        assert row["status"] == "running"

    def test_fail_review(self, temp_db):
        review_id = create_review("{}", db_path=temp_db)
        fail_review(review_id, "LLM timeout", db_path=temp_db)

        row = get_review(review_id, db_path=temp_db)
        assert row["status"] == "failed"

    def test_list_reviews(self, temp_db):
        for i in range(5):
            create_review(json.dumps({"index": i}), db_path=temp_db)

        reviews = list_reviews(limit=3, db_path=temp_db)
        assert len(reviews) == 3

    def test_get_nonexistent_review(self, temp_db):
        row = get_review("nonexistent-id", db_path=temp_db)
        assert row is None

    def test_feedback_crud(self, temp_db):
        review_id = create_review("{}", db_path=temp_db)

        fb_id = save_feedback(review_id, "finding-1", True, "Good catch", db_path=temp_db)
        assert fb_id is not None

        save_feedback(review_id, "finding-2", False, db_path=temp_db)

        stats = get_feedback_stats(db_path=temp_db)
        assert stats["total"] == 2
        assert stats["accepted"] == 1
        assert stats["rejected"] == 1
        assert stats["acceptance_rate"] == 50.0

    def test_empty_feedback_stats(self, temp_db):
        stats = get_feedback_stats(db_path=temp_db)
        assert stats["total"] == 0
        assert stats["acceptance_rate"] == 0.0
