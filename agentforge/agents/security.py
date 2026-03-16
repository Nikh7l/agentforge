"""Security Review Agent — focuses on vulnerability detection."""

from agentforge.agents.base import BaseReviewAgent
from agentforge.config import SECURITY_SYSTEM_PROMPT


class SecurityAgent(BaseReviewAgent):
    name = "security"
    system_prompt = SECURITY_SYSTEM_PROMPT
