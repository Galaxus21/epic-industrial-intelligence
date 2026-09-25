"""
EPIC — Agent Tool Registry (WP-4)
Executes the ReAct investigator's tools (schemas in toolDefinitions.py) over verified platform services, and names
the evidence each result contains. Every tool reads; none writes.
1. get_maintenance_records (db_service)
2. get_compliance (db_service)
3. search_similar_incidents (vector_service)
4. search_relevant_docs (vector_service)
5. traverse_neighbours (knowledge_graph)
6. detect_stored_anomalies (anomalyService / WP-1)
7. get_equipment_status (db_service, with alarmEvaluation for each reading's status)

A model-chosen number is clamped to the bounds its schema states, and an unusable one falls back to the default.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable, Iterable

from app.agents.toolDefinitions import (
    DOCUMENT_LIMIT, INCIDENT_LIMIT, TOOL_DEFINITIONS, TRAVERSE_DEPTH, TRAVERSE_LIMIT, Bound,
)
from app.services import db_service as db
from app.services import vector_service as vs
from app.services.alarmEvaluation import readingStatuses
from app.services.knowledge_graph import graph_service
from app.services.anomalyService import detect_stored_anomalies

__all__ = ["TOOL_DEFINITIONS", "TOOL_RUNNERS", "execute_tool", "extract_evidence_ids"]

logger = logging.getLogger(__name__)

EQUIPMENT_STATUS_KEYS = (
    "id", "name", "type", "status", "criticality", "location",
    "health_score", "failure_probability", "maintenance_due_days",
)


# ─── Tool Execution Wrappers ──────────────────────────────────────────────────

async def _wrap_get_maintenance_records(args: dict[str, Any]) -> list[dict[str, Any]]:
    return await db.get_maintenance_records(_requiredText(args, "equipment_id"))


async def _wrap_get_compliance(args: dict[str, Any]) -> dict[str, Any] | None:
    return await db.get_compliance(_requiredText(args, "equipment_id"))


async def _wrap_search_similar_incidents(args: dict[str, Any]) -> dict[str, Any]:
    return await vs.search_similar_incidents(
        query=_requiredText(args, "query"), equipment_id=_optionalText(args, "equipment_id"),
        limit=_boundedInt(args, "limit", INCIDENT_LIMIT),
    )


async def _wrap_search_relevant_docs(args: dict[str, Any]) -> dict[str, Any]:
    return await vs.search_relevant_docs(
        query=_requiredText(args, "query"), equipment_id=_optionalText(args, "equipment_id"),
        limit=_boundedInt(args, "limit", DOCUMENT_LIMIT),
    )


async def _wrap_traverse_neighbours(args: dict[str, Any]) -> dict[str, Any]:
    return await graph_service.traverse_neighbours(
        equipment_id=_requiredText(args, "equipment_id"),
        max_depth=_boundedInt(args, "max_depth", TRAVERSE_DEPTH), limit=_boundedInt(args, "limit", TRAVERSE_LIMIT),
    )


async def _wrap_detect_stored_anomalies(args: dict[str, Any]) -> dict[str, Any]:
    return await detect_stored_anomalies(_requiredText(args, "equipment_id"))


async def _wrap_get_equipment_status(args: dict[str, Any]) -> dict[str, Any]:
    equipmentId = _requiredText(args, "equipment_id")
    equipment = await db.get_equipment(equipmentId)
    if equipment is None:
        return {"error": f"Equipment '{equipmentId}' not found"}
    readings = equipment.get("current_readings") or {}
    statuses = readingStatuses(readings)
    return {
        **{key: equipment.get(key) for key in EQUIPMENT_STATUS_KEYS},
        "readings": {key: {**reading, "status": statuses[key]} for key, reading in readings.items() if key in statuses},
    }


TOOL_RUNNERS: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {
    "get_maintenance_records": _wrap_get_maintenance_records,
    "get_compliance": _wrap_get_compliance,
    "search_similar_incidents": _wrap_search_similar_incidents,
    "search_relevant_docs": _wrap_search_relevant_docs,
    "traverse_neighbours": _wrap_traverse_neighbours,
    "detect_stored_anomalies": _wrap_detect_stored_anomalies,
    "get_equipment_status": _wrap_get_equipment_status,
}


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Execute a registered agent tool by name with provided arguments."""
    runner = TOOL_RUNNERS.get(tool_name)
    if not runner:
        logger.warning("Attempted to execute unregistered tool: %s", tool_name)
        return {"error": f"Tool '{tool_name}' is not recognized in registry"}
    try:
        return await runner(arguments)
    except Exception as exc:
        logger.warning("Tool execution error in %s: %s", tool_name, exc, exc_info=True)
        return {"error": f"Tool '{tool_name}' failed: {str(exc)}"}


def extract_evidence_ids(tool_name: str, result: Any) -> set[str]:
    """Extract verifiable evidence identifiers (doc_id, incident_id, record id) from tool outputs."""
    if not result or isinstance(result, Exception) or (isinstance(result, dict) and "error" in result):
        return set()
    extractor = EVIDENCE_EXTRACTORS.get(tool_name)
    return {str(identifier) for identifier in extractor(result) if identifier} if extractor else set()


# ─── Evidence extraction, one function per tool result shape ─────────────────

def _items(result: Any) -> list[dict[str, Any]]:
    items = result.get("items") if isinstance(result, dict) else result
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _recordIds(result: Any) -> Iterable[Any]:
    return [record.get("id") for record in _items(result)]


def _complianceIds(result: Any) -> Iterable[Any]:
    if not isinstance(result, dict):
        return []
    issues = [issue for issue in result.get("issues") or [] if isinstance(issue, dict)]
    return [result.get("id"), result.get("equipment_id"), *(issue.get("id") for issue in issues)]


def _incidentIds(result: Any) -> Iterable[Any]:
    return [incident.get("incident_id") or incident.get("id") for incident in _items(result)]


def _documentIds(result: Any) -> Iterable[Any]:
    return [value for doc in _items(result) for value in (doc.get("doc_id") or doc.get("id"), doc.get("document"))]


def _nodeIds(result: Any) -> Iterable[Any]:
    nodes = result.get("nodes") if isinstance(result, dict) else None
    return [node.get("id") for node in nodes or [] if isinstance(node, dict)]


def _equipmentId(result: Any) -> Iterable[Any]:
    return [result.get("equipment_id") or result.get("id")] if isinstance(result, dict) else []


EVIDENCE_EXTRACTORS: dict[str, Callable[[Any], Iterable[Any]]] = {
    "get_maintenance_records": _recordIds,
    "get_compliance": _complianceIds,
    "search_similar_incidents": _incidentIds,
    "search_relevant_docs": _documentIds,
    "traverse_neighbours": _nodeIds,
    "detect_stored_anomalies": _equipmentId,
    "get_equipment_status": _equipmentId,
}


def _requiredText(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise ValueError(f"Missing required parameter '{key}'")
    return value


def _optionalText(args: dict[str, Any], key: str) -> str | None:
    return str(args.get(key) or "").strip() or None


def _boundedInt(args: dict[str, Any], key: str, bound: Bound) -> int:
    try:
        value = int(args.get(key, bound.default))
    except (TypeError, ValueError):
        return bound.default
    return min(max(value, bound.lowest), bound.highest)
