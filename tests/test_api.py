"""Tests for the FastAPI endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agentforge.api.app import create_app
from agentforge.models.database import create_review


@pytest.fixture
def client(temp_db):
    """Create a test FastAPI client with temp database."""
    with (
        patch("agentforge.api.app.init_db"),
        patch("agentforge.models.database.DB_PATH", temp_db),
        patch(
            "agentforge.services.review_service.create_review",
            side_effect=lambda req, **kw: create_review(req, db_path=temp_db),
        ),
        patch("agentforge.api.routes.review.execute_review"),
    ):
        app = create_app()
        yield TestClient(app)


class TestHealthEndpoint:
    def test_health(self):
        app = create_app()
        with TestClient(app) as c:
            r = c.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"


class TestReviewEndpoints:
    def test_submit_review(self, client):
        r = client.post(
            "/api/review",
            json={
                "code": "print('hello')",
                "filename": "test.py",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "review_id" in data
        assert data["status"] == "pending"

    def test_submit_review_no_code(self, client):
        r = client.post(
            "/api/review",
            json={
                "filename": "test.py",
            },
        )
        assert r.status_code == 422  # Validation error

    def test_get_nonexistent_review(self, client):
        r = client.get("/api/review/nonexistent-id")
        assert r.status_code == 404
