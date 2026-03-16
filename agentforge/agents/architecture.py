"""Architecture Review Agent — focuses on design quality and SOLID principles."""

from agentforge.agents.base import BaseReviewAgent
from agentforge.config import ARCHITECTURE_SYSTEM_PROMPT


class ArchitectureAgent(BaseReviewAgent):
    name = "architecture"
    system_prompt = ARCHITECTURE_SYSTEM_PROMPT
