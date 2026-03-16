"""Tests for the CLI commands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from agentforge.cli.main import app

runner = CliRunner()


class TestCLICommands:
    """Test CLI commands via Typer's test runner."""

    def test_review_file_not_found(self):
        result = runner.invoke(app, ["review", "/nonexistent/file.py"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_history_empty(self, temp_db):
        with patch("agentforge.cli.main.list_reviews", return_value=[]), patch("agentforge.cli.main.init_db"):
            result = runner.invoke(app, ["history"])
            assert result.exit_code == 0
            assert "no reviews" in result.output.lower()

    def test_stats_command(self):
        with patch("agentforge.cli.main.init_db"):
            with patch("agentforge.cli.main.get_collection_stats", return_value={"indexed": False, "count": 0}):
                result = runner.invoke(app, ["stats"])
                assert result.exit_code == 0
                assert "0" in result.output

    def test_index_not_a_directory(self):
        result = runner.invoke(app, ["index", "/nonexistent/dir"])
        assert result.exit_code == 1
        assert "not a directory" in result.output.lower()

    def test_history_with_reviews(self, temp_db):
        mock_reviews = [
            {
                "id": "abc-123",
                "status": "completed",
                "created_at": "2026-01-01T00:00:00",
                "completed_at": "2026-01-01T00:01:00",
            },
            {"id": "def-456", "status": "pending", "created_at": "2026-01-01T00:02:00", "completed_at": None},
        ]
        with patch("agentforge.cli.main.list_reviews", return_value=mock_reviews):
            with patch("agentforge.cli.main.init_db"):
                result = runner.invoke(app, ["history"])
                assert result.exit_code == 0
                assert "abc-123" in result.output
                assert "def-456" in result.output
