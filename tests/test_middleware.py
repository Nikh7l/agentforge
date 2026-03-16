"""Tests for security middleware."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from agentforge.api.app import create_app


class TestAPIKeyMiddleware:
    """Test API key authentication."""

    def test_no_keys_configured_allows_all(self):
        with patch("agentforge.api.middleware.API_KEYS", set()), patch("agentforge.api.app.init_db"):
            app = create_app()
            with TestClient(app) as client:
                r = client.get("/health")
                assert r.status_code == 200

    def test_health_is_public(self):
        with patch("agentforge.api.middleware.API_KEYS", {"test-key-123"}), patch("agentforge.api.app.init_db"):
            app = create_app()
            with TestClient(app) as client:
                r = client.get("/health")
                assert r.status_code == 200

    def test_missing_key_returns_401(self):
        with patch("agentforge.api.middleware.API_KEYS", {"test-key-123"}), patch("agentforge.api.app.init_db"):
            app = create_app()
            with TestClient(app) as client:
                r = client.get("/api/reviews")
                assert r.status_code == 401

    def test_valid_key_succeeds(self):
        with patch("agentforge.api.middleware.API_KEYS", {"test-key-123"}), patch("agentforge.api.app.init_db"):
            with patch("agentforge.services.review_service.list_reviews", return_value=[]):
                app = create_app()
                with TestClient(app) as client:
                    r = client.get("/api/reviews", headers={"X-API-Key": "test-key-123"})
                    assert r.status_code == 200

    def test_invalid_key_returns_401(self):
        with patch("agentforge.api.middleware.API_KEYS", {"test-key-123"}), patch("agentforge.api.app.init_db"):
            app = create_app()
            with TestClient(app) as client:
                r = client.get("/api/reviews", headers={"X-API-Key": "wrong-key"})
                assert r.status_code == 401


class TestRateLimiting:
    """Test rate limit middleware."""

    def test_rate_limit_enforced(self):
        with patch("agentforge.api.middleware.API_KEYS", set()):
            with patch("agentforge.api.middleware.RATE_LIMIT_RPM", 3):
                with patch("agentforge.api.app.init_db"):
                    with patch("agentforge.services.review_service.list_reviews", return_value=[]):
                        app = create_app()
                        with TestClient(app) as client:
                            # First 3 should succeed
                            for _ in range(3):
                                r = client.get("/api/reviews")
                                assert r.status_code == 200

                            # 4th should be rate limited
                            r = client.get("/api/reviews")
                            assert r.status_code == 429
                            assert "Rate limit" in r.json()["detail"]
