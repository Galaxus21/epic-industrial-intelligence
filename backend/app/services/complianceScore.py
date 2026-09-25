"""
EPIC — The compliance score an equipment's open issues add up to.

One rule for the compliance retriever (app/agents/orchestrator.py) and the demo seed, so a seeded score is the score
the retriever derives from the same issues.
"""
from __future__ import annotations

from typing import Any

SEVERITY_PENALTY = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
UNRATED_PENALTY = SEVERITY_PENALTY["Medium"]
FULL_SCORE = 100
COMPLIANT_FROM = 90
WARNING_FROM = 75
NON_COMPLIANT_FROM = 50


def complianceScore(issues: list[dict[str, Any]]) -> tuple[int, str]:
    """(score, status) after taking each open issue's severity penalty off a full score."""
    penalty = sum(SEVERITY_PENALTY.get(issue.get("severity", "Medium"), UNRATED_PENALTY) for issue in issues)
    score = max(0, FULL_SCORE - penalty)
    if score >= COMPLIANT_FROM:
        return score, "Compliant"
    if score >= WARNING_FROM:
        return score, "Warning"
    if score >= NON_COMPLIANT_FROM:
        return score, "Non-Compliant"
    return score, "Critical"
