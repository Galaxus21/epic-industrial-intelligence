"""
EPIC — When the equipment a question names ends the query before any retrieval runs.

Two cases get a plain answer instead of an analysis:
1. The question names a tag that is not in the equipment register. Analysing it would present empty context as
   findings about equipment that does not exist.
2. The question names several registered tags on a route that analyses one asset at a time. A multi-hop
   investigation is plant-wide and follows the links between assets, so several tags do not stop it.
"""
from __future__ import annotations

from typing import Any

from app.services.equipmentResolver import ResolutionResult

MULTI_ASSET_ROUTES = frozenset({"multi_hop", "react"})
UNKNOWN_RISK_LEVEL = "Unknown"

StopEvent = tuple[str, str, str, dict[str, Any]]


def scopeStopEvents(resolution: ResolutionResult, route: str) -> list[StopEvent] | None:
    """The (agent, status, message, data) events that end the query, or None when it can go on."""
    if resolution.is_unknown:
        return _unknownTagEvents(resolution.candidates)
    if resolution.is_ambiguous and route not in MULTI_ASSET_ROUTES:
        return _ambiguousEvents(resolution.candidates)
    return None


def _unknownTagEvents(tags: list[str]) -> list[StopEvent]:
    names = ", ".join(tags)
    message = (
        f"**{names}** is not in the equipment register, so there is nothing recorded to analyse.\n\n"
        "Check the tag on the Equipment page, or register the equipment first."
    )
    return [
        ("equipment_brain", "done", f"Not registered equipment: {names}.", {"unknown_equipment": tags}),
        ("synthesizer", "done", f"{names} is not registered equipment.", {
            "response_type": "chat",
            "message": message,
            "unknown_equipment": tags,
            "risk_level": UNKNOWN_RISK_LEVEL,
            "risk_summary": f"Not registered equipment: {names}",
        }),
    ]


def _ambiguousEvents(candidates: list[str]) -> list[StopEvent]:
    names = ", ".join(candidates)
    message = (
        f"Your inquiry matches multiple assets in the plant: **{names}**.\n\n"
        "Please specify which equipment you would like to inspect."
    )
    return [
        ("equipment_brain", "done", f"Ambiguous query: matches {len(candidates)} equipment tags ({names}).",
         {"ambiguous": True, "candidates": candidates}),
        ("synthesizer", "done", f"Query matches multiple equipment ({names}). Please clarify your target asset.", {
            "response_type": "chat",
            "message": message,
            "ambiguous": True,
            "candidates": candidates,
            "risk_level": UNKNOWN_RISK_LEVEL,
            "risk_summary": f"Ambiguous query matching: {names}",
        }),
    ]
