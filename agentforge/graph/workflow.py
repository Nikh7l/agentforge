"""LangGraph workflow — orchestrates the multi-agent review pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from agentforge.agents.architecture import ArchitectureAgent
from agentforge.agents.autofix import AutoFixAgent
from agentforge.agents.correctness import CorrectnessAgent
from agentforge.agents.performance import PerformanceAgent
from agentforge.agents.router import RouterAgent
from agentforge.agents.security import SecurityAgent
from agentforge.agents.synthesizer import SynthesizerAgent
from agentforge.models.schemas import (
    AgentReport,
    FixSuggestionSchema,
    RoutingDecision,
    SynthesizedReview,
)

logger = logging.getLogger(__name__)

# ── Agent registry ─────────────────────────────────────────────────────

AGENT_MAP = {
    "security": SecurityAgent,
    "performance": PerformanceAgent,
    "architecture": ArchitectureAgent,
    "correctness": CorrectnessAgent,
}


# ── Graph State ────────────────────────────────────────────────────────


def _merge_reports(existing: list[AgentReport], new: list[AgentReport]) -> list[AgentReport]:
    """Reducer: merge new reports into existing list."""
    return existing + new


class ReviewState(TypedDict):
    """State that flows through the review graph."""

    code: str
    filename: str
    context: str
    routing: RoutingDecision | None
    agent_reports: Annotated[list[AgentReport], _merge_reports]
    final_review: SynthesizedReview | None


# ── Node functions ─────────────────────────────────────────────────────


async def route_node(state: ReviewState) -> dict:
    """Classify the code and decide which agents to activate."""
    router = RouterAgent()
    decision = await router.route(state["code"], state["filename"])
    logger.info(
        f"Router decided: lang={decision.language}, domain={decision.domain}, agents={decision.agents_to_activate}"
    )
    return {"routing": decision}


async def review_node(state: ReviewState) -> dict:
    """Run all selected review agents in parallel."""
    routing = state["routing"]
    if routing is None:
        return {"agent_reports": []}

    agents_to_run = []
    for agent_name in routing.agents_to_activate:
        if agent_name in AGENT_MAP:
            agents_to_run.append(AGENT_MAP[agent_name]())

    if not agents_to_run:
        return {"agent_reports": []}

    # Run all agents concurrently
    context = state.get("context", "") or ""
    tasks = [agent.review(state["code"], context) for agent in agents_to_run]
    reports = await asyncio.gather(*tasks, return_exceptions=True)

    valid_reports = []
    for report in reports:
        if isinstance(report, Exception):
            logger.error(f"Agent failed with exception: {report}")
            valid_reports.append(AgentReport(agent_name="unknown", findings=[], summary="", error=str(report)))
        else:
            valid_reports.append(report)

    logger.info(f"Completed {len(valid_reports)} agent reviews")
    return {"agent_reports": valid_reports}


async def synthesize_node(state: ReviewState) -> dict:
    """Synthesize all agent reports into a unified review."""
    synthesizer = SynthesizerAgent()
    review = await synthesizer.synthesize(state["agent_reports"], state["code"])
    logger.info(f"Synthesis complete: score={review.overall_score}")
    return {"final_review": review}


async def autofix_node(state: ReviewState) -> dict:
    """Generate fix suggestions for all findings."""
    review = state.get("final_review")
    if review is None or not review.findings:
        return {"final_review": review}

    autofix = AutoFixAgent()
    suggestion = await autofix.generate_fix(
        code=state["code"],
        findings=review.findings,
        filename=state["filename"],
    )

    # Attach fix suggestion to the review
    review.fix_suggestion = FixSuggestionSchema(
        fixed_code=suggestion.fixed_code,
        changes_summary=suggestion.changes_summary,
        findings_addressed=suggestion.findings_addressed,
    )

    logger.info(f"Auto-fix generated: {suggestion.findings_addressed} findings addressed")
    return {"final_review": review}


# ── Graph construction ─────────────────────────────────────────────────


def build_review_graph() -> StateGraph:
    """Build and compile the review workflow graph."""
    graph = StateGraph(ReviewState)

    # Add nodes
    graph.add_node("route", route_node)
    graph.add_node("review", review_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("autofix", autofix_node)

    # Flow: route → review (parallel agents) → synthesize → autofix
    graph.add_edge(START, "route")
    graph.add_edge("route", "review")
    graph.add_edge("review", "synthesize")
    graph.add_edge("synthesize", "autofix")
    graph.add_edge("autofix", END)

    return graph.compile()


# ── Convenience runner ─────────────────────────────────────────────────


async def run_review(code: str, filename: str = "untitled.py", context: str = "") -> SynthesizedReview:
    """Run a full code review and return the synthesized result."""
    graph = build_review_graph()

    initial_state: ReviewState = {
        "code": code,
        "filename": filename,
        "context": context,
        "routing": None,
        "agent_reports": [],
        "final_review": None,
    }

    result = await graph.ainvoke(initial_state)
    return result["final_review"]
