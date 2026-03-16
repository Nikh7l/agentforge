"""Auto-Fix Agent — generates code patches as suggestions for each finding."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agentforge.config import MODEL_NAME, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, TEMPERATURE
from agentforge.models.schemas import AgentFinding

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0

AUTOFIX_SYSTEM_PROMPT = """\
You are an expert code fixer. Given a code snippet and a list of findings (bugs, vulnerabilities, \
performance issues, design problems), generate a FIXED version of the code.

Rules:
1. Fix ALL findings listed — do not skip any.
2. Preserve the original code's intent and structure as much as possible.
3. Add clear inline comments (prefixed with "# FIX:") next to each change explaining what was fixed and why.
4. If a finding cannot be fully fixed in-place (e.g., requires a new dependency or a broader refactor), \
   add a "# TODO:" comment explaining what else needs to be done.
5. Return ONLY the fixed code — no markdown fences, no explanations outside the code.
6. Keep the same indentation style as the original.
"""


@dataclass(slots=True)
class FixSuggestion:
    """A suggested fix for a code file."""

    original_code: str
    fixed_code: str
    changes_summary: str
    findings_addressed: int


class AutoFixAgent:
    """Generates code patches as suggestions based on review findings."""

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

    async def generate_fix(
        self,
        code: str,
        findings: list[AgentFinding | dict],
        filename: str = "untitled.py",
    ) -> FixSuggestion:
        """Generate a fixed version of the code addressing all findings.

        Returns a FixSuggestion with the original code, fixed code, and summary.
        """
        prompt = self._build_prompt(code, findings, filename)

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self.llm.invoke,
                    [
                        SystemMessage(content=AUTOFIX_SYSTEM_PROMPT),
                        HumanMessage(content=prompt),
                    ],
                )
                fixed_code = self._clean_response(response.content)
                summary = self._generate_summary(findings)

                return FixSuggestion(
                    original_code=code,
                    fixed_code=fixed_code,
                    changes_summary=summary,
                    findings_addressed=len(findings),
                )

            except Exception as e:
                logger.warning(f"[AutoFix] Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BASE_DELAY * (2**attempt))
                else:
                    return FixSuggestion(
                        original_code=code,
                        fixed_code=code,
                        changes_summary=f"Auto-fix failed: {e}",
                        findings_addressed=0,
                    )

        return FixSuggestion(
            original_code=code,
            fixed_code=code,
            changes_summary="Auto-fix failed: unknown error",
            findings_addressed=0,
        )

    def _build_prompt(self, code: str, findings: list[AgentFinding | dict], filename: str) -> str:
        """Build the prompt with code and findings."""
        parts = [
            f"## File: {filename}\n",
            f"```\n{code}\n```\n",
            "\n## Findings to Fix\n",
        ]

        for i, finding in enumerate(findings, 1):
            if isinstance(finding, dict):
                sev = finding.get("severity", "info")
                cat = finding.get("category", "")
                desc = finding.get("description", "")
                lines = f"Lines {finding.get('line_start', '?')}-{finding.get('line_end', '?')}"
                fix = finding.get("suggested_fix", "")
            else:
                sev = finding.severity.value if hasattr(finding.severity, "value") else finding.severity
                cat = finding.category
                desc = finding.description
                lines = f"Lines {finding.line_start}-{finding.line_end}"
                fix = finding.suggested_fix

            parts.append(f"{i}. **[{sev.upper()}] {cat}** ({lines})")
            parts.append(f"   {desc}")
            if fix:
                parts.append(f"   Suggested approach: {fix}")
            parts.append("")

        parts.append(
            "\nGenerate the complete fixed file. "
            "Include ALL original code (not just the changed parts). "
            "Add '# FIX:' comments next to each change."
        )
        return "\n".join(parts)

    def _clean_response(self, text: str) -> str:
        """Strip markdown fences from LLM response."""
        cleaned = text.strip()
        # Remove markdown code fences
        for lang in (
            "```python",
            "```py",
            "```javascript",
            "```js",
            "```typescript",
            "```ts",
            "```java",
            "```go",
            "```rust",
            "```cpp",
            "```c",
            "```",
        ):
            if cleaned.startswith(lang):
                cleaned = cleaned[len(lang) :]
                break
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _generate_summary(self, findings: list[AgentFinding | dict]) -> str:
        """Create a human-readable summary of what was fixed."""
        counts = {"critical": 0, "warning": 0, "info": 0}
        for f in findings:
            if isinstance(f, dict):
                sev = f.get("severity", "info")
            else:
                sev = f.severity.value if hasattr(f.severity, "value") else f.severity
            counts[sev] = counts.get(sev, 0) + 1

        parts = []
        for sev, count in counts.items():
            if count > 0:
                parts.append(f"{count} {sev}")
        return f"Addressed {', '.join(parts)} finding(s)."
