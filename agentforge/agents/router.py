"""Router Agent — classifies code and decides which reviewers to activate."""

from __future__ import annotations

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agentforge.config import MODEL_NAME, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, ROUTER_SYSTEM_PROMPT, TEMPERATURE
from agentforge.models.schemas import Complexity, Domain, RiskLevel, RoutingDecision

logger = logging.getLogger(__name__)

VALID_AGENTS = {"security", "performance", "architecture", "correctness"}


class RouterAgent:
    """Classifies code and determines which specialized agents to invoke."""

    name = "router"

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

    async def route(self, code: str, filename: str = "") -> RoutingDecision:
        """Analyze code and return a routing decision."""
        prompt = (
            f"## Code to Classify\n"
            f"Filename: {filename}\n\n"
            f"```\n{code}\n```\n\n"
            f"Return a JSON object with: language, domain, complexity, risk_level, agents_to_activate.\n"
            f"Valid agents: {sorted(VALID_AGENTS)}\n"
            f"Return ONLY the JSON — no markdown, no commentary."
        )

        try:
            response = await asyncio.to_thread(
                self.llm.invoke,
                [
                    SystemMessage(content=ROUTER_SYSTEM_PROMPT),
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

            # Normalize and validate agents
            agents = [a for a in data.get("agents_to_activate", []) if a in VALID_AGENTS]
            if "correctness" not in agents:
                agents.append("correctness")

            return RoutingDecision(
                language=data.get("language", "unknown"),
                domain=data.get("domain", "general"),
                complexity=data.get("complexity", "medium"),
                risk_level=data.get("risk_level", "medium"),
                agents_to_activate=agents,
            )

        except Exception as e:
            logger.error(f"Router failed, using defaults: {e}")
            # Fallback: activate all agents
            return RoutingDecision(
                language=_guess_language(filename),
                domain=Domain.GENERAL,
                complexity=Complexity.MEDIUM,
                risk_level=RiskLevel.MEDIUM,
                agents_to_activate=list(VALID_AGENTS),
            )


def _guess_language(filename: str) -> str:
    """Simple language detection from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
    }
    for ext, lang in ext_map.items():
        if filename.endswith(ext):
            return lang
    return "unknown"
