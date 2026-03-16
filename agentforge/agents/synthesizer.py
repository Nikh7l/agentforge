"""Synthesizer Agent — merges multiple agent reports into a unified review."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agentforge.config import (
    MODEL_NAME,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    SYNTHESIZER_SYSTEM_PROMPT,
    TEMPERATURE,
)
from agentforge.models.schemas import (
    AgentFinding,
    AgentReport,
    ConflictResolution,
    SynthesizedReview,
)

logger = logging.getLogger(__name__)


class SynthesizerAgent:
    """Merges reports from specialized agents into a single, deduplicated review."""

    name = "synthesizer"

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=TEMPERATURE,
            default_headers={
                "HTTP-Referer": "https://agentforge.dev",
                "X-Title": "AgentForge",
            },
        )

    async def synthesize(self, reports: list[AgentReport], code: str) -> SynthesizedReview:
        """Merge all agent reports and produce a final synthesized review."""
        # Build a detailed prompt with all reports
        report_sections = []
        for report in reports:
            if report.error:
                report_sections.append(f"### {report.agent_name} Agent\n**ERROR**: {report.error}\n")
                continue

            findings_text = json.dumps([f.model_dump() for f in report.findings], indent=2)
            report_sections.append(
                f"### {report.agent_name} Agent\n"
                f"**Summary**: {report.summary}\n"
                f"**Findings**:\n```json\n{findings_text}\n```\n"
            )

        prompt = (
            f"## Code Under Review\n```\n{code}\n```\n\n"
            f"## Agent Reports\n\n{''.join(report_sections)}\n\n"
            f"## Instructions\n"
            f"Synthesize the above reports into a unified review.\n\n"
            f"Return a JSON object:\n"
            f"```json\n"
            f"{{\n"
            f'  "overall_score": 0-100,\n'
            f'  "summary": "Executive summary",\n'
            f'  "findings": [\n'
            f"    {{\n"
            f'      "id": "unique-id",\n'
            f'      "severity": "critical|warning|info",\n'
            f'      "category": "string",\n'
            f'      "description": "string",\n'
            f'      "line_start": 0,\n'
            f'      "line_end": 0,\n'
            f'      "suggested_fix": "string"\n'
            f"    }}\n"
            f"  ],\n"
            f'  "conflicts": [\n'
            f"    {{\n"
            f'      "agents_involved": ["agent1", "agent2"],\n'
            f'      "description": "What they disagreed on",\n'
            f'      "resolution": "How you resolved it"\n'
            f"    }}\n"
            f"  ]\n"
            f"}}\n"
            f"```\n"
            f"Return ONLY the JSON."
        )

        try:
            response = await asyncio.to_thread(
                self.llm.invoke,
                [
                    SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ],
            )
            text = response.content.strip()

            # Clean markdown fences
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.index("```") + 3
                end = text.index("```", start)
                text = text[start:end].strip()

            data = json.loads(text)

            # Parse findings with IDs
            findings = []
            for item in data.get("findings", []):
                if not item.get("id"):
                    item["id"] = str(uuid.uuid4())[:8]
                try:
                    findings.append(AgentFinding(**item))
                except Exception:  # noqa: S112
                    continue

            # Parse conflicts
            conflicts = []
            for item in data.get("conflicts", []):
                try:
                    conflicts.append(ConflictResolution(**item))
                except Exception:  # noqa: S112
                    continue

            return SynthesizedReview(
                overall_score=data.get("overall_score", 50),
                summary=data.get("summary", "Review completed."),
                findings=findings,
                conflicts=conflicts,
                agent_reports=reports,
            )

        except Exception as e:
            logger.error(f"Synthesizer failed: {e}")
            # Fallback: merge all findings as-is
            all_findings = []
            for report in reports:
                for finding in report.findings:
                    finding.id = finding.id or str(uuid.uuid4())[:8]
                    all_findings.append(finding)

            return SynthesizedReview(
                overall_score=50,
                summary=f"Synthesis failed ({e}). Showing raw findings from all agents.",
                findings=all_findings,
                conflicts=[],
                agent_reports=reports,
            )
