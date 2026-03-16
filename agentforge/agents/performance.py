"""Performance Review Agent — focuses on efficiency and optimization."""

from agentforge.agents.base import BaseReviewAgent
from agentforge.config import PERFORMANCE_SYSTEM_PROMPT


class PerformanceAgent(BaseReviewAgent):
    name = "performance"
    system_prompt = PERFORMANCE_SYSTEM_PROMPT
