"""Tests for the AutoFix agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentforge.agents.autofix import AutoFixAgent
from agentforge.models.schemas import AgentFinding, Severity


class TestAutoFixAgent:
    """Test auto-fix agent behavior."""

    @pytest.mark.asyncio
    async def test_generate_fix_returns_suggestion(self):
        """Test that the agent returns a fix suggestion."""
        mock_response = MagicMock()
        mock_response.content = "# FIX: Use parameterized query\nimport sqlite3\n\ndef get_user(user_id):\n    conn = sqlite3.connect('db.sqlite')\n    # FIX: Parameterized query prevents SQL injection\n    cursor = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))\n    return cursor.fetchone()\n"

        with patch.object(AutoFixAgent, "__init__", lambda self: None):
            agent = AutoFixAgent()
            agent.llm = MagicMock()
            agent.llm.invoke.return_value = mock_response

            finding = AgentFinding(
                severity=Severity.CRITICAL,
                category="SQL Injection",
                description="User input in SQL query",
                line_start=3,
                line_end=5,
                suggested_fix="Use parameterized queries",
            )

            result = await agent.generate_fix(
                code="import sqlite3\n\ndef get_user(user_id):\n    conn = sqlite3.connect('db.sqlite')\n    cursor = conn.execute(f'SELECT * FROM users WHERE id = {user_id}')\n    return cursor.fetchone()\n",
                findings=[finding],
                filename="db.py",
            )

        assert result.findings_addressed == 1
        assert "FIX:" in result.fixed_code
        assert result.changes_summary != ""

    @pytest.mark.asyncio
    async def test_generate_fix_handles_dict_findings(self):
        """Test that dict-format findings are handled."""
        mock_response = MagicMock()
        mock_response.content = "fixed_code_here"

        with patch.object(AutoFixAgent, "__init__", lambda self: None):
            agent = AutoFixAgent()
            agent.llm = MagicMock()
            agent.llm.invoke.return_value = mock_response

            finding_dict = {
                "severity": "warning",
                "category": "Performance",
                "description": "O(n^2) loop",
                "line_start": 1,
                "line_end": 5,
                "suggested_fix": "Use set lookup",
            }

            result = await agent.generate_fix(
                code="for x in list1:\n    for y in list2:\n        if x == y:\n            print(x)",
                findings=[finding_dict],
                filename="slow.py",
            )

        assert result.findings_addressed == 1
        assert result.fixed_code == "fixed_code_here"

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self):
        """Test that markdown code fences are stripped from response."""
        mock_response = MagicMock()
        mock_response.content = "```python\nprint('fixed')\n```"

        with patch.object(AutoFixAgent, "__init__", lambda self: None):
            agent = AutoFixAgent()
            agent.llm = MagicMock()
            agent.llm.invoke.return_value = mock_response

            result = await agent.generate_fix(
                code="print('broken')",
                findings=[{"severity": "info", "category": "Bug", "description": "test"}],
            )

        assert "```" not in result.fixed_code
        assert "print('fixed')" in result.fixed_code
