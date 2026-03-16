"""Base abstraction for all review agents."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agentforge.config import MODEL_NAME, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, TEMPERATURE
from agentforge.models.schemas import AgentFinding, AgentReport

logger = logging.getLogger(__name__)

# Maximum retries with exponential backoff
MAX_RETRIES = 3
BASE_DELAY = 1.0


def _get_llm() -> ChatOpenAI:
    """Create a configured LLM instance via OpenRouter."""
    return ChatOpenAI(
        model=MODEL_NAME,
        openai_api_key=OPENROUTER_API_KEY,
        openai_api_base=OPENROUTER_BASE_URL,
        temperature=TEMPERATURE,
        default_headers={
            "HTTP-Referer": "https://agentforge.dev",
            "X-Title": "AgentForge",
        },
    )


def _parse_findings_from_text(text: str) -> list[AgentFinding]:
    """Extract findings from LLM text response — handles JSON in markdown blocks."""
    # Try to find a JSON array in the text
    cleaned = text.strip()

    # Remove markdown code fences if present
    if "```json" in cleaned:
        start = cleaned.index("```json") + 7
        end = cleaned.index("```", start)
        cleaned = cleaned[start:end].strip()
    elif "```" in cleaned:
        start = cleaned.index("```") + 3
        end = cleaned.index("```", start)
        cleaned = cleaned[start:end].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find any JSON array
        import re

        arr_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if arr_match:
            try:
                data = json.loads(arr_match.group())
            except json.JSONDecodeError:
                return []
        else:
            # Try to find JSON object with findings key
            obj_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if obj_match:
                try:
                    data = json.loads(obj_match.group())
                    if isinstance(data, dict):
                        data = data.get("findings", [data])
                except json.JSONDecodeError:
                    return []
            else:
                return []

    # Normalize to list
    if isinstance(data, dict):
        data = data.get("findings", [data])

    findings = []
    for item in data:
        if isinstance(item, dict):
            try:
                findings.append(AgentFinding(**item))
            except Exception:  # noqa: S112
                # Skip malformed findings
                continue
    return findings


class BaseReviewAgent(ABC):
    """Abstract base class for all specialized review agents.

    Subclasses must define `name` and `system_prompt`.
    The `review` method handles LLM invocation with retry logic.
    """

    name: str
    system_prompt: str

    def __init__(self) -> None:
        self.llm = _get_llm()

    async def review(self, code: str, context: str = "") -> AgentReport:
        """Run the review with retry logic and structured output parsing."""
        prompt = self._build_prompt(code, context)

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self.llm.invoke,
                    [
                        SystemMessage(content=self.system_prompt),
                        HumanMessage(content=prompt),
                    ],
                )
                text = response.content
                findings = _parse_findings_from_text(text)
                summary = self._extract_summary(text, findings)

                return AgentReport(
                    agent_name=self.name,
                    findings=findings,
                    summary=summary,
                )

            except Exception as e:
                logger.warning(f"[{self.name}] Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BASE_DELAY * (2**attempt))
                else:
                    return AgentReport(
                        agent_name=self.name,
                        findings=[],
                        summary="",
                        error=f"Agent failed after {MAX_RETRIES} retries: {e!s}",
                    )

        # Unreachable, but satisfies type checker
        return AgentReport(agent_name=self.name, findings=[], summary="", error="Unknown error")

    def _build_prompt(self, code: str, context: str) -> str:
        """Build the user prompt to send to the LLM."""
        parts = [
            "## Code to Review\n",
            f"```\n{code}\n```\n",
        ]
        if context:
            parts.append(f"\n## Additional Context\n{context}\n")

        parts.append(
            "\n## Response Format\n"
            "Return a JSON object with the following structure:\n"
            "```json\n"
            "{\n"
            '  "findings": [\n'
            "    {\n"
            '      "severity": "critical" | "warning" | "info",\n'
            '      "category": "string",\n'
            '      "description": "string",\n'
            '      "line_start": 0,\n'
            '      "line_end": 0,\n'
            '      "suggested_fix": "string"\n'
            "    }\n"
            "  ],\n"
            '  "summary": "Brief summary of your analysis"\n'
            "}\n"
            "```\n"
            "If there are no issues, return an empty findings array with a positive summary."
        )
        return "\n".join(parts)

    def _extract_summary(self, text: str, findings: list[AgentFinding]) -> str:
        """Try to extract a summary from the LLM response."""
        try:
            cleaned = text.strip()
            if "```json" in cleaned:
                start = cleaned.index("```json") + 7
                end = cleaned.index("```", start)
                cleaned = cleaned[start:end].strip()
            elif "```" in cleaned:
                start = cleaned.index("```") + 3
                end = cleaned.index("```", start)
                cleaned = cleaned[start:end].strip()

            data = json.loads(cleaned)
            if isinstance(data, dict) and "summary" in data:
                return data["summary"]
        except Exception:  # noqa: S110
            pass

        # Fallback summary
        if not findings:
            return f"No issues found by {self.name} agent."
        counts = {"critical": 0, "warning": 0, "info": 0}
        for f in findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        parts = []
        for sev, count in counts.items():
            if count > 0:
                parts.append(f"{count} {sev}")
        return f"Found {', '.join(parts)} issue(s)."
