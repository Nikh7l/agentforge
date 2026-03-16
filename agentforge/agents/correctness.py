"""Correctness Review Agent — focuses on logic errors and edge cases."""

from agentforge.agents.base import BaseReviewAgent
from agentforge.config import CORRECTNESS_SYSTEM_PROMPT


class CorrectnessAgent(BaseReviewAgent):
    name = "correctness"
    system_prompt = CORRECTNESS_SYSTEM_PROMPT
