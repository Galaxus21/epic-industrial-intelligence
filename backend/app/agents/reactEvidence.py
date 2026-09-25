"""
EPIC — How much tool evidence the ReAct investigator reads, and in what form.

The local model's window is 10,240 tokens (backend/ollama/epicChat.Modelfile), and Ollama drops the start of an
over-long prompt without an error, which would take the system prompt and its untrusted-content rules with it. So:
- each tool result enters the loop as compact JSON cut at TOOL_RESULT_CHARS;
- once LOOP_EVIDENCE_CHARS of results have been read, further tool calls are answered with a note instead of run,
  the loop stops, and the answer's risk_summary says the investigation is partial (flagBudgetReached);
- the final synthesis reads every result, not a preview, each given an equal share of SYNTHESIS_EVIDENCE_CHARS.
The heaviest loop request measured, five steps through all seven tools on the P-101 demo data with a full history,
was 6,738 prompt tokens for Qwen 2.5 (Ollama prompt_tokens, 2026-09-25; about 2.5 characters per token for this
JSON), which leaves room for the model's 1,500-token turn.
"""
from __future__ import annotations

from typing import Any

from app.services.promptContext import promptJson

TOOL_RESULT_CHARS = 3000
LOOP_EVIDENCE_CHARS = 15000
SYNTHESIS_EVIDENCE_CHARS = 12000
TRUNCATION_MARK = " …[truncated]"
BUDGET_REACHED_NOTE = '{"error":"Evidence budget for this investigation is used up; conclude with what you have."}'
BUDGET_SUMMARY_PREFIX = "[Evidence budget reached: partial investigation] "


class EvidenceBudget:
    """The characters of tool output the loop may still show the model."""

    def __init__(self) -> None:
        self.remaining = LOOP_EVIDENCE_CHARS

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    def take(self, result: Any) -> str:
        text = boundedJson(result, min(TOOL_RESULT_CHARS, self.remaining))
        self.remaining -= len(text)
        return text


def boundedJson(value: Any, limit: int) -> str:
    text = promptJson(value)
    if len(text) <= limit:
        return text
    return text[:max(limit - len(TRUNCATION_MARK), 0)] + TRUNCATION_MARK


def synthesisEvidence(calls: list[dict[str, Any]]) -> str:
    """Every tool call followed by its result, each result given an equal share of SYNTHESIS_EVIDENCE_CHARS."""
    share = SYNTHESIS_EVIDENCE_CHARS // max(len(calls), 1)
    return "\n".join(
        promptJson({"step": call["step"], "tool": call["tool"], "args": call["args"]}) + "\n"
        + boundedJson(call["result"], share)
        for call in calls
    )


def flagBudgetReached(result: dict[str, Any]) -> None:
    """Say in the answer itself that the investigation is partial, whatever the model wrote."""
    summary = result.get("risk_summary") or ""
    if not summary.startswith(BUDGET_SUMMARY_PREFIX):
        result["risk_summary"] = BUDGET_SUMMARY_PREFIX + summary
