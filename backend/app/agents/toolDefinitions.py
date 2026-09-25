"""
EPIC — The tools the ReAct investigator may call, as OpenAI-compatible function schemas.

Every tool reads; none writes. A numeric argument carries the bounds toolRegistry clamps it to, so the model is told
the same limits that are enforced: a model-chosen limit must not pull an unbounded result into the prompt.
"""
from __future__ import annotations

from typing import Any, NamedTuple


class Bound(NamedTuple):
    default: int
    lowest: int
    highest: int


INCIDENT_LIMIT = Bound(4, 1, 8)
DOCUMENT_LIMIT = Bound(6, 1, 8)
TRAVERSE_DEPTH = Bound(2, 1, 3)
TRAVERSE_LIMIT = Bound(50, 1, 50)

EQUIPMENT_ID = {"type": "string",
                "description": "Tag of a registered equipment item, exactly as the query or an earlier tool result writes it."}
OPTIONAL_EQUIPMENT_ID = {"type": "string", "description": "Optional equipment ID to narrow the search."}


def _boundedInteger(description: str, bound: Bound) -> dict[str, Any]:
    return {"type": "integer", "description": description, "default": bound.default,
            "minimum": bound.lowest, "maximum": bound.highest}


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    _tool("get_maintenance_records",
          "Maintenance records for an equipment item, newest first: completed, scheduled and overdue work with findings.",
          {"equipment_id": EQUIPMENT_ID}, ["equipment_id"]),
    _tool("get_compliance",
          "The site compliance record for an equipment item: open issues, each with its id (CI-…) and the standard "
          "it is judged against, passed checks, and the score.",
          {"equipment_id": EQUIPMENT_ID}, ["equipment_id"]),
    _tool("search_similar_incidents",
          "Semantically search recorded incidents, lessons from completed work orders and defects for matching "
          "symptoms, root causes or lessons learned.",
          {"query": {"type": "string", "description": "Symptoms, anomalies or failure mechanisms to match."},
           "equipment_id": OPTIONAL_EQUIPMENT_ID,
           "limit": _boundedInteger("Maximum number of incidents to return.", INCIDENT_LIMIT)},
          ["query"]),
    _tool("search_relevant_docs",
          "Semantically search stored documents (uploaded reports, manuals, shift handovers and work-order records) "
          "for relevant sections.",
          {"query": {"type": "string", "description": "What to look for: specifications, limits or procedures."},
           "equipment_id": OPTIONAL_EQUIPMENT_ID,
           "limit": _boundedInteger("Maximum number of document sections to return.", DOCUMENT_LIMIT)},
          ["query"]),
    _tool("traverse_neighbours",
          "Multi-hop traversal of the plant knowledge graph from an equipment node: connected equipment, incidents, "
          "work orders, documents and technicians.",
          {"equipment_id": EQUIPMENT_ID,
           "max_depth": _boundedInteger("Maximum traversal depth in hops.", TRAVERSE_DEPTH),
           "limit": _boundedInteger("Maximum connected nodes to return.", TRAVERSE_LIMIT)},
          ["equipment_id"]),
    _tool("detect_stored_anomalies",
          "Statistical anomaly detection (Isolation Forest and IQR) over stored sensor history, to find anomalies "
          "and drift.",
          {"equipment_id": EQUIPMENT_ID}, ["equipment_id"]),
    _tool("get_equipment_status",
          "The current state of one equipment item: each live sensor reading with its normal, alarm and trip limits "
          "and alarm status, plus operating status, criticality, health score, failure probability and days until "
          "maintenance is due.",
          {"equipment_id": EQUIPMENT_ID}, ["equipment_id"]),
]
