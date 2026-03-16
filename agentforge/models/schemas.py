"""Pydantic models — shared data contracts for the entire system."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ── Enums ──────────────────────────────────────────────────────────────


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Domain(str, Enum):
    WEB = "web"
    DATA = "data"
    INFRASTRUCTURE = "infrastructure"
    ML = "ml"
    GENERAL = "general"


class Complexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Request Models ─────────────────────────────────────────────────────


class ReviewRequest(BaseModel):
    """Input model for a code review request."""

    code: str = Field(..., description="The source code to review")
    filename: str = Field(default="untitled.py", description="Name of the file")
    language: str | None = Field(default=None, description="Programming language (auto-detected if not set)")
    context: str | None = Field(default=None, description="Additional context about the codebase")


# ── Routing ────────────────────────────────────────────────────────────


class RoutingDecision(BaseModel):
    """Output from the Router Agent."""

    language: str = Field(..., description="Detected programming language")
    domain: Domain = Field(..., description="Code domain classification")
    complexity: Complexity = Field(..., description="Code complexity level")
    risk_level: RiskLevel = Field(..., description="Risk level for potential issues")
    agents_to_activate: list[str] = Field(
        ...,
        description="List of agent names to activate: security, performance, architecture, correctness",
    )


# ── Agent Findings ─────────────────────────────────────────────────────


class AgentFinding(BaseModel):
    """A single finding from a review agent."""

    id: str | None = Field(default=None, description="Unique finding ID (assigned by synthesizer)")
    severity: Severity = Field(..., description="Issue severity")
    category: str = Field(..., description="Sub-category of the finding")
    description: str = Field(..., description="Clear explanation of the issue")
    line_start: int = Field(default=0, description="Start line number (0 if unknown)")
    line_end: int = Field(default=0, description="End line number (0 if unknown)")
    suggested_fix: str = Field(default="", description="Concrete fix or mitigation")


class AgentReport(BaseModel):
    """Full output from a single review agent."""

    agent_name: str = Field(..., description="Name of the agent that produced this report")
    findings: list[AgentFinding] = Field(default_factory=list, description="List of findings")
    summary: str = Field(default="", description="Brief summary of the agent's review")
    error: str | None = Field(default=None, description="Error message if the agent failed")


# ── Synthesized Review ─────────────────────────────────────────────────


class ConflictResolution(BaseModel):
    """Records a conflict between agents and how it was resolved."""

    agents_involved: list[str] = Field(..., description="Which agents disagreed")
    description: str = Field(..., description="What the conflict was about")
    resolution: str = Field(..., description="How it was resolved and why")


class FixSuggestionSchema(BaseModel):
    """Auto-generated code fix suggestion."""

    fixed_code: str = Field(default="", description="The suggested fixed code")
    changes_summary: str = Field(default="", description="Summary of what was changed")
    findings_addressed: int = Field(default=0, description="Number of findings addressed")


class SynthesizedReview(BaseModel):
    """Final merged review from the Synthesizer Agent."""

    overall_score: int = Field(..., ge=0, le=100, description="Code quality score 0-100")
    summary: str = Field(..., description="Executive summary of the review")
    findings: list[AgentFinding] = Field(default_factory=list, description="Deduplicated, prioritized findings")
    conflicts: list[ConflictResolution] = Field(default_factory=list, description="Resolved conflicts")
    agent_reports: list[AgentReport] = Field(default_factory=list, description="Raw reports from each agent")
    fix_suggestion: FixSuggestionSchema | None = Field(default=None, description="Auto-generated fix suggestion")


# ── Feedback ───────────────────────────────────────────────────────────


class FeedbackItem(BaseModel):
    """User feedback on a single finding."""

    finding_id: str = Field(..., description="ID of the finding being rated")
    accepted: bool = Field(..., description="Whether the user accepted this finding")
    comment: str | None = Field(default=None, description="Optional user comment")
