"""Tests for Pydantic schemas and data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentforge.models.schemas import (
    AgentFinding,
    AgentReport,
    Complexity,
    ConflictResolution,
    Domain,
    FeedbackItem,
    ReviewRequest,
    RiskLevel,
    RoutingDecision,
    Severity,
    SynthesizedReview,
)


class TestSchemas:
    """Test Pydantic model validation."""

    def test_review_request_minimal(self):
        req = ReviewRequest(code="print('hello')")
        assert req.filename == "untitled.py"
        assert req.language is None

    def test_review_request_full(self):
        req = ReviewRequest(
            code="x = 1",
            filename="app.py",
            language="python",
            context="Flask application",
        )
        assert req.language == "python"

    def test_review_request_requires_code(self):
        with pytest.raises(ValidationError):
            ReviewRequest()

    def test_routing_decision(self):
        rd = RoutingDecision(
            language="python",
            domain=Domain.WEB,
            complexity=Complexity.HIGH,
            risk_level=RiskLevel.HIGH,
            agents_to_activate=["security", "correctness"],
        )
        assert len(rd.agents_to_activate) == 2

    def test_agent_finding(self):
        f = AgentFinding(
            severity=Severity.CRITICAL,
            category="SQL Injection",
            description="User input directly concatenated into SQL query",
            line_start=12,
            line_end=14,
            suggested_fix="Use parameterized queries",
        )
        assert f.severity == Severity.CRITICAL
        assert f.line_start == 12

    def test_agent_report(self):
        report = AgentReport(
            agent_name="security",
            findings=[
                AgentFinding(severity=Severity.WARNING, category="test", description="test finding"),
            ],
            summary="Found 1 warning",
        )
        assert len(report.findings) == 1
        assert report.error is None

    def test_synthesized_review_score_bounds(self):
        # Valid score
        review = SynthesizedReview(
            overall_score=85,
            summary="Good code",
            findings=[],
        )
        assert review.overall_score == 85

        # Invalid scores
        with pytest.raises(ValidationError):
            SynthesizedReview(overall_score=-1, summary="Bad", findings=[])

        with pytest.raises(ValidationError):
            SynthesizedReview(overall_score=101, summary="Bad", findings=[])

    def test_conflict_resolution(self):
        cr = ConflictResolution(
            agents_involved=["security", "performance"],
            description="Security recommends hashing, performance says it's slow",
            resolution="Use bcrypt with reasonable work factor — security takes priority",
        )
        assert len(cr.agents_involved) == 2

    def test_feedback_item(self):
        fb = FeedbackItem(
            finding_id="abc123",
            accepted=True,
            comment="Great catch!",
        )
        assert fb.accepted is True
