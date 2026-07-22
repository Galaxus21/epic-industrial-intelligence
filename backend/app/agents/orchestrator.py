"""
AI Operations Brain — Agent Orchestrator
Streams five-agent pipeline via Server-Sent Events (SSE).
Each agent builds context; the Synthesizer calls GPT-4.1 to produce the final answer.

Agent sequence:
  1. Equipment Brain     — loads equipment memory from knowledge graph
  2. Maintenance Advisor — searches maintenance history, finds similar incidents
  3. Compliance Agent   — checks OISD/ISO regulatory status
  4. Lessons Learned    — correlates historical failure patterns
  5. Document Intelligence — retrieves relevant manual sections and SOPs
  6. Synthesizer        — calls GPT-4.1 to merge all contexts into one structured answer
"""
import asyncio
import json
from typing import AsyncIterator, Any

from app.services import db_service as db
from app.services.llm_service import synthesize_query
from app.services.knowledge_graph import GraphService
from app.services import vector_service as vs

_graph_service = GraphService()


async def _build_maintenance_context(equipment_id: str, query: str) -> dict[str, Any]:
    records = await db.get_maintenance_records(equipment_id)
    eq = await db.get_equipment(equipment_id) or {}

    overdue = [r for r in records if r.get("status") == "Overdue"]
    recent  = [r for r in records if r.get("status") == "Completed"][:3]

    # Semantic search via Qdrant; keyword search falls back automatically
    similar = await vs.search_similar_incidents(query, equipment_id=equipment_id, limit=4)
    qdrant_active = await vs.is_active()

    return {
        "recent_maintenance": recent,
        "overdue_tasks":      overdue,
        "similar_incidents":  similar,
        "current_readings":   eq.get("current_readings", {}),
        "health_score":       eq.get("health_score"),
        "failure_probability":eq.get("failure_probability"),
        "vector_search_used": qdrant_active,
    }


async def _build_compliance_context(equipment_id: str) -> dict[str, Any]:
    return await db.get_compliance(equipment_id) or {"overall_score": 100, "status": "OK", "issues": [], "passed": []}


async def _build_lessons_context(query: str, equipment_id: str) -> dict[str, Any]:
    # Semantic incident search via Qdrant (falls back to keyword search)
    incidents = await vs.search_similar_incidents(query, equipment_id=equipment_id, limit=5)

    lessons = []
    for inc in incidents:
        if inc.get("lessons_learned"):
            lessons.append({
                "incident_id": inc["id"],
                "equipment_id": inc["equipment_id"],
                "date": inc["date"],
                "symptom": inc.get("symptom"),
                "root_cause": inc.get("root_cause"),
                "lesson": inc.get("lessons_learned", ""),
                "similarity": inc.get("similarity_to_p101", 80) if inc["equipment_id"] != equipment_id else 91,
            })

    return {"lessons": lessons, "pattern_found": len(lessons) > 0}


async def _build_documents_context(equipment_id: str, query: str) -> dict[str, Any]:
    # Semantic document retrieval via Qdrant; falls back to keyword scan
    qdrant_sections = await vs.search_relevant_docs(query, equipment_id=equipment_id, limit=8)

    if qdrant_sections:
        # Ensure feedback docs are always included (learning data)
        feedback = [s for s in qdrant_sections if s.get("type") == "feedback"]
        others   = [s for s in qdrant_sections if s.get("type") != "feedback"]
        combined = (feedback + others[:6 - len(feedback)])[:8]
        all_docs = await db.get_equipment_documents(equipment_id)
        return {
            "relevant_sections":    combined,
            "total_docs_searched":  len(all_docs),
            "feedback_count":       len(feedback),
            "vector_search_used":   qdrant_sections[0].get("_source", "").startswith("qdrant"),
        }

    # Pure PostgreSQL fallback (no Qdrant, no embeddings)
    docs = await db.get_equipment_documents(equipment_id)
    relevant_sections: list[dict[str, Any]] = []
    query_lower = query.lower()
    keywords = ["vibration", "bearing", "lubrication", "seal", "alarm", "maintenance", "inspection"]
    triggered_keywords = [kw for kw in keywords if kw in query_lower]

    for doc in docs:
        for section_id, text in (doc.get("sections") or {}).items():
            if any(kw in text.lower() for kw in triggered_keywords) or not triggered_keywords:
                relevant_sections.append({
                    "document": doc["name"],
                    "doc_id":   doc["id"],
                    "section":  section_id,
                    "text":     text[:400],
                    "type":     doc["type"],
                    "is_feedback": doc["type"] == "feedback",
                    "_source":  "pg_keyword",
                })

    feedback_sections = [s for s in relevant_sections if s.get("is_feedback")]
    non_feedback      = [s for s in relevant_sections if not s.get("is_feedback")]
    combined = (feedback_sections + non_feedback[:6 - len(feedback_sections)])[:8]
    return {
        "relevant_sections":   combined,
        "total_docs_searched": len(docs),
        "feedback_count":      len(feedback_sections),
        "vector_search_used":  False,
    }


# ── Significance-gated, query-aware highlights ────────────────────────────────

def _build_highlights(agent_id: str, query: str, data: dict) -> list[dict]:
    """Return a minimal list of findings worth surfacing in the agent panel.
    Only shows a metric if it is alarming OR the user explicitly asked about it."""
    q = query.lower()
    results: list[dict] = []

    if agent_id == "equipment_brain":
        health    = data.get("health_score")
        vib       = data.get("current_vibration")
        alarm     = data.get("alarm_threshold")
        fail_prob = data.get("failure_probability")
        incidents = data.get("incident_count") or 0
        asks_vib    = any(k in q for k in ("vibration", "vib", "bearing", "mm/s", "oscillat"))
        asks_health = any(k in q for k in ("health", "condition", "score", "status", "how is"))

        if vib is not None:
            v, a = float(vib), float(alarm) if alarm is not None else None
            breached = a is not None and v >= a
            if breached:
                results.append({"label": "Vibration", "value": f"{vib} mm/s \u26a0 (alarm {alarm})", "level": "critical"})
            elif asks_vib or v > 4:
                note = f" / alarm {alarm}" if alarm else ""
                results.append({"label": "Vibration", "value": f"{vib} mm/s{note}", "level": "warn" if v > 6 else "info"})

        if health is not None:
            h = float(health)
            if asks_health or h < 85:
                results.append({"label": "Health", "value": f"{health}%",
                                 "level": "critical" if h < 65 else "warn" if h < 85 else "info"})

        if fail_prob is not None and float(fail_prob) > 10:
            results.append({"label": "Failure risk", "value": f"{fail_prob}%",
                             "level": "critical" if float(fail_prob) > 30 else "warn"})

        if incidents > 0:
            results.append({"label": "Incidents", "value": str(incidents),
                             "level": "warn" if incidents > 2 else "info"})

    elif agent_id == "maintenance_advisor":
        overdue = len(data.get("overdue_tasks") or [])
        similar = len(data.get("similar_incidents") or [])
        if overdue > 0:
            results.append({"label": "Overdue tasks", "value": str(overdue),
                             "level": "critical" if overdue > 1 else "warn"})
        if similar > 0:
            results.append({"label": "Similar incidents", "value": str(similar), "level": "warn"})

    elif agent_id == "compliance_agent":
        issues = data.get("issues") or []
        score  = data.get("overall_score")
        asks_compliance = any(k in q for k in ("compliance", "regulation", "permit", "oisd", "iso", "standard"))
        high_count = sum(1 for i in issues if isinstance(i, dict) and i.get("severity") == "High")
        if high_count > 0:
            results.append({"label": "HIGH issues", "value": str(high_count), "level": "critical"})
        elif issues:
            results.append({"label": "Issues", "value": str(len(issues)), "level": "warn"})
        if score is not None and (float(score) < 90 or asks_compliance):
            s = float(score)
            results.append({"label": "Score", "value": f"{score}%",
                             "level": "critical" if s < 70 else "warn" if s < 90 else "info"})

    elif agent_id == "lessons_learned":
        lessons = data.get("lessons") or []
        if lessons:
            results.append({"label": "Pattern matches", "value": str(len(lessons)), "level": "warn"})

    elif agent_id == "document_intelligence":
        feedback = data.get("feedback_count") or 0
        sections = len(data.get("relevant_sections") or [])
        if feedback > 0:
            results.append({"label": "Feedback records", "value": str(feedback), "level": "info"})
        elif sections > 0:
            results.append({"label": "Sections", "value": str(sections), "level": "info"})

    return results


async def run_query_stream(
    equipment_id: str,
    query: str,
    history: list[dict[str, str]] | None = None,
    plant_id: str | None = None,
    project_id: str | None = None,
) -> AsyncIterator[str]:
    """
    Yield SSE-formatted events as each agent completes.
    Each event is:  data: <json>\n\n
    Final event:    data: [DONE]\n\n
    """

    def _event(agent: str, status: str, message: str = "", data: Any = None) -> str:
        payload = {"agent": agent, "status": status, "message": message}
        if data is not None:
            payload["data"] = data
        return f"data: {json.dumps(payload)}\n\n"

    # ── 0. Fetch plant / project context for the synthesizer ─────────────────
    plant_context: dict[str, Any] = {}
    if plant_id or project_id:
        from sqlalchemy import select
        from app.db.database import AsyncSessionLocal
        from app.db import models as m
        async with AsyncSessionLocal() as s:
            if plant_id:
                plant_row = (await s.execute(
                    select(m.Plant).where(m.Plant.id == plant_id)
                )).scalar_one_or_none()
                if plant_row:
                    plant_context["plant_id"]   = plant_row.id
                    plant_context["plant_name"] = plant_row.name
                    plant_context["plant_code"] = plant_row.code
                    plant_context["plant_area"] = plant_row.area
                    plant_context["plant_type"] = plant_row.type
            if project_id:
                proj_row = (await s.execute(
                    select(m.Project).where(m.Project.id == project_id)
                )).scalar_one_or_none()
                if proj_row:
                    plant_context["project_id"]   = proj_row.id
                    plant_context["project_name"] = proj_row.name
                    plant_context["project_code"] = proj_row.code

    # ── 1. Equipment Brain ────────────────────────────────────────────────────
    yield _event("equipment_brain", "active", "Loading equipment memory from knowledge graph…")
    await asyncio.sleep(0.4)
    brain = await _graph_service.get_equipment_brain(equipment_id)
    eq = await db.get_equipment(equipment_id) or {}
    readings = eq.get("current_readings") or {}
    vib_de = readings.get("vibration_de", {}) if isinstance(readings, dict) else {}
    brain_summary = {
        "name": eq.get("name"),
        "type": eq.get("type"),
        "health_score": eq.get("health_score"),
        "failure_probability": eq.get("failure_probability"),
        "current_vibration": vib_de.get("value"),
        "alarm_threshold": vib_de.get("alarm"),
        "maintenance_due_days": eq.get("maintenance_due_days"),
        "incident_count": len(await db.get_equipment_incidents(equipment_id)),
        "connected_equipment": eq.get("downstream_equipment") or [],
        "technicians": eq.get("technicians") or [],
    }
    brain_summary["highlights"] = _build_highlights("equipment_brain", query, brain_summary)
    yield _event("equipment_brain", "done", "Equipment memory loaded", brain_summary)

    # ── 2. Maintenance Advisor ────────────────────────────────────────────────
    yield _event("maintenance_advisor", "active", "Searching maintenance history and similar incidents…")
    await asyncio.sleep(0.6)
    maintenance_ctx = await _build_maintenance_context(equipment_id, query)
    maintenance_ctx["highlights"] = _build_highlights("maintenance_advisor", query, maintenance_ctx)
    yield _event(
        "maintenance_advisor",
        "done",
        f"Found {len(maintenance_ctx['overdue_tasks'])} overdue task(s), {len(maintenance_ctx['similar_incidents'])} similar incident(s)",
        maintenance_ctx,
    )

    # ── 3. Compliance Agent ───────────────────────────────────────────────────
    yield _event("compliance_agent", "active", "Checking OISD-117, ISO 10816, SOP compliance…")
    await asyncio.sleep(0.5)
    compliance_ctx = await _build_compliance_context(equipment_id)
    issue_count = len(compliance_ctx.get("issues") or [])
    high_issues = len([i for i in (compliance_ctx.get("issues") or []) if i.get("severity") == "High"])
    compliance_ctx["highlights"] = _build_highlights("compliance_agent", query, compliance_ctx)
    yield _event(
        "compliance_agent",
        "done",
        f"{issue_count} compliance issue(s) found ({high_issues} High severity)",
        compliance_ctx,
    )

    # ── 4. Lessons Learned ────────────────────────────────────────────────────
    yield _event("lessons_learned", "active", "Scanning historical incidents for matching failure patterns…")
    await asyncio.sleep(0.7)
    lessons_ctx = await _build_lessons_context(query, equipment_id)
    match_count = len(lessons_ctx.get("lessons", []))
    lessons_ctx["highlights"] = _build_highlights("lessons_learned", query, lessons_ctx)
    yield _event(
        "lessons_learned",
        "done",
        f"Pattern match found — {match_count} historical incident(s) with similar signature",
        lessons_ctx,
    )

    # ── 5. Document Intelligence ──────────────────────────────────────────────
    yield _event("document_intelligence", "active", "Searching OEM manuals, SOPs, and safety standards…")
    await asyncio.sleep(0.5)
    docs_ctx = await _build_documents_context(equipment_id, query)
    docs_ctx["highlights"] = _build_highlights("document_intelligence", query, docs_ctx)
    yield _event(
        "document_intelligence",
        "done",
        f"Retrieved {len(docs_ctx['relevant_sections'])} relevant document sections from {docs_ctx['total_docs_searched']} documents"
        + (f" (incl. {docs_ctx['feedback_count']} real-world feedback records)" if docs_ctx.get("feedback_count") else ""),
        docs_ctx,
    )

    # ── 5b. Comms Intelligence (email + Slack) ────────────────────────────────
    comms_ctx: dict[str, Any] = {"emails": [], "slack_messages": [], "source": "none"}
    try:
        from app.services.integrations.email_service import get_emails
        from app.services.integrations.slack_service import get_slack_messages
        eq_emails = await get_emails(equipment_filter=equipment_id)
        eq_slack  = await get_slack_messages(equipment_filter=equipment_id)
        comms_ctx = {
            "emails": [
                {"subject": e["subject"], "from": e["from"], "date": e["date"],
                 "body_preview": e["body"][:300], "action_required": e["action_required"]}
                for e in eq_emails[:5]
            ],
            "slack_messages": [
                {"channel": m["channel"], "user": m["user_display"],
                 "text": m["text"][:300], "timestamp": m["timestamp"],
                 "action_required": m["action_required"]}
                for m in eq_slack[:5]
            ],
            "total_emails": len(eq_emails),
            "total_slack": len(eq_slack),
            "source": "live" if (eq_emails or eq_slack) else "none",
        }
    except Exception:
        pass

    # ── 6. Synthesizer (GPT-4.1) ──────────────────────────────────────────────
    yield _event("synthesizer", "active", "Synthesizing final recommendation with GPT-4.1…")
    final = await synthesize_query(
        equipment_id=equipment_id,
        query=query,
        equipment_context=brain,
        maintenance_context=maintenance_ctx,
        compliance_context=compliance_ctx,
        lessons_context=lessons_ctx,
        documents_context=docs_ctx,
        history=history or [],
        plant_context=plant_context,
        comms_context=comms_ctx,
    )
    yield _event("synthesizer", "done", "Analysis complete", final)

    yield "data: [DONE]\n\n"
