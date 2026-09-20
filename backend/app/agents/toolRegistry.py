"""
EPIC — Agent Tool Registry (WP-4)
Defines OpenAI-compatible tool schemas and asynchronous execution wrappers for
verified platform services:
1. get_maintenance_records (db_service)
2. get_compliance (db_service)
3. search_similar_incidents (vector_service)
4. search_relevant_docs (vector_service)
5. traverse_neighbours (knowledge_graph)
6. detect_stored_anomalies (anomalyService / WP-1)
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from app.services import db_service as db
from app.services import vector_service as vs
from app.services.knowledge_graph import graph_service
from app.services.anomalyService import detect_stored_anomalies

logger = logging.getLogger(__name__)

# ─── OpenAI Tool Definitions ──────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_maintenance_records",
            "description": (
                "Retrieve historical maintenance records, work orders, repair logs, "
                "and scheduled tasks for an equipment item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {
                        "type": "string",
                        "description": "Equipment tag ID (e.g. 'P-101', 'K-401').",
                    },
                },
                "required": ["equipment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_compliance",
            "description": (
                "Retrieve regulatory compliance status, standards violations (OISD, ISO 10816, "
                "SOP requirements), and active safety permits for an equipment item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {
                        "type": "string",
                        "description": "Equipment tag ID (e.g. 'P-101', 'K-401').",
                    },
                },
                "required": ["equipment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_incidents",
            "description": (
                "Semantically search historical plant incident reports and failure logs "
                "for matching symptoms, root causes, or lessons learned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query describing symptoms, anomalies, or failure mechanisms.",
                    },
                    "equipment_id": {
                        "type": "string",
                        "description": "Optional equipment ID to narrow search scope.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of incidents to return (default: 4).",
                        "default": 4,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_relevant_docs",
            "description": (
                "Semantically search OEM technical manuals, operating procedures (SOPs), "
                "inspection reports, and industry standards for relevant sections."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for technical specifications, tolerances, or procedures.",
                    },
                    "equipment_id": {
                        "type": "string",
                        "description": "Optional equipment ID to narrow search scope.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of document sections to return (default: 6).",
                        "default": 6,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traverse_neighbours",
            "description": (
                "Perform multi-hop graph traversal in the plant knowledge graph starting from "
                "an equipment node to discover upstream/downstream connections, shared piping, and dependencies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {
                        "type": "string",
                        "description": "Starting equipment ID (e.g. 'P-101').",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum traversal depth in hops (default: 2).",
                        "default": 2,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum connected nodes/links to return (default: 50).",
                        "default": 50,
                    },
                },
                "required": ["equipment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_stored_anomalies",
            "description": (
                "Execute ML statistical anomaly detection (multivariate Isolation Forest & IQR) "
                "over stored historical telemetry to uncover anomalies and drift patterns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {
                        "type": "string",
                        "description": "Equipment ID to run anomaly detection against (e.g. 'P-101').",
                    },
                },
                "required": ["equipment_id"],
            },
        },
    },
]


# ─── Tool Execution Wrappers ──────────────────────────────────────────────────

async def _wrap_get_maintenance_records(args: dict[str, Any]) -> list[dict[str, Any]]:
    equipment_id = str(args.get("equipment_id") or "").strip()
    if not equipment_id:
        raise ValueError("Missing required parameter 'equipment_id'")
    return await db.get_maintenance_records(equipment_id)


async def _wrap_get_compliance(args: dict[str, Any]) -> dict[str, Any] | None:
    equipment_id = str(args.get("equipment_id") or "").strip()
    if not equipment_id:
        raise ValueError("Missing required parameter 'equipment_id'")
    return await db.get_compliance(equipment_id)


async def _wrap_search_similar_incidents(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        raise ValueError("Missing required parameter 'query'")
    equipment_id = args.get("equipment_id")
    if equipment_id:
        equipment_id = str(equipment_id).strip() or None
    limit = int(args.get("limit", 4))
    res = await vs.search_similar_incidents(query=query, equipment_id=equipment_id, limit=limit)
    if isinstance(res, dict):
        return res
    # Fallback to dict if unexpected type
    return {"items": list(res), "source": "vector_service", "degraded": False}


async def _wrap_search_relevant_docs(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        raise ValueError("Missing required parameter 'query'")
    equipment_id = args.get("equipment_id")
    if equipment_id:
        equipment_id = str(equipment_id).strip() or None
    limit = int(args.get("limit", 6))
    res = await vs.search_relevant_docs(query=query, equipment_id=equipment_id, limit=limit)
    if isinstance(res, dict):
        return res
    return {"items": list(res), "source": "vector_service", "degraded": False}


async def _wrap_traverse_neighbours(args: dict[str, Any]) -> dict[str, Any]:
    equipment_id = str(args.get("equipment_id") or "").strip()
    if not equipment_id:
        raise ValueError("Missing required parameter 'equipment_id'")
    max_depth = int(args.get("max_depth", 2))
    limit = int(args.get("limit", 50))
    return await graph_service.traverse_neighbours(equipment_id=equipment_id, max_depth=max_depth, limit=limit)


async def _wrap_detect_stored_anomalies(args: dict[str, Any]) -> dict[str, Any]:
    equipment_id = str(args.get("equipment_id") or "").strip()
    if not equipment_id:
        raise ValueError("Missing required parameter 'equipment_id'")
    return await detect_stored_anomalies(equipment_id)


TOOL_RUNNERS: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {
    "get_maintenance_records": _wrap_get_maintenance_records,
    "get_compliance": _wrap_get_compliance,
    "search_similar_incidents": _wrap_search_similar_incidents,
    "search_relevant_docs": _wrap_search_relevant_docs,
    "traverse_neighbours": _wrap_traverse_neighbours,
    "detect_stored_anomalies": _wrap_detect_stored_anomalies,
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


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return all tool definitions formatted for OpenAI tool calling."""
    return TOOL_DEFINITIONS


def extract_evidence_ids(tool_name: str, result: Any) -> set[str]:
    """Extract verifiable evidence identifiers (doc_id, incident_id, record id) from tool outputs."""
    evidence_ids: set[str] = set()
    if not result or isinstance(result, Exception):
        return evidence_ids

    if isinstance(result, dict) and "error" in result:
        return evidence_ids

    if tool_name == "get_maintenance_records":
        if isinstance(result, list):
            for r in result:
                if isinstance(r, dict) and r.get("id"):
                    evidence_ids.add(str(r["id"]))
    elif tool_name == "get_compliance":
        if isinstance(result, dict):
            if result.get("id"):
                evidence_ids.add(str(result["id"]))
            if result.get("equipment_id"):
                evidence_ids.add(str(result["equipment_id"]))
            for issue in result.get("issues") or []:
                if isinstance(issue, dict) and issue.get("code"):
                    evidence_ids.add(str(issue["code"]))
    elif tool_name == "search_similar_incidents":
        items = result.get("items") if isinstance(result, dict) else result
        if isinstance(items, list):
            for inc in items:
                if isinstance(inc, dict):
                    inc_id = inc.get("incident_id") or inc.get("id")
                    if inc_id:
                        evidence_ids.add(str(inc_id))
    elif tool_name == "search_relevant_docs":
        items = result.get("items") if isinstance(result, dict) else result
        if isinstance(items, list):
            for doc in items:
                if isinstance(doc, dict):
                    if doc.get("ai_generated") is False or "generation unavailable" in (doc.get("document") or "").lower():
                        continue
                    did = doc.get("doc_id") or doc.get("id")
                    if did:
                        evidence_ids.add(str(did))
                    if doc.get("document"):
                        evidence_ids.add(str(doc["document"]))
    elif tool_name == "traverse_neighbours":
        if isinstance(result, dict):
            for node in result.get("nodes") or []:
                if isinstance(node, dict) and node.get("id"):
                    evidence_ids.add(str(node["id"]))
    elif tool_name == "detect_stored_anomalies":
        if isinstance(result, dict) and result.get("equipment_id"):
            evidence_ids.add(str(result["equipment_id"]))

    return evidence_ids
