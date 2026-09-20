"""
AI Operations Brain — Agent Orchestrator
Streams the retrieval + synthesis pipeline via Server-Sent Events (SSE).

The five specialist retrievers (equipment brain, maintenance, compliance,
lessons, documents) run CONCURRENTLY via asyncio.gather — they are independent
database/vector lookups. Their results are then merged by a single LLM
synthesis call. Events are still streamed per-specialist so the UI can show
progress, but there are no artificial delays.
"""
import asyncio
from datetime import date, datetime
import json
import logging
from typing import AsyncIterator, Any

from app.services import db_service as db
from app.services.equipmentResolver import resolve_equipment
from app.services.llm_service import (
    synthesize_query,
    classify_query_intent,
    synthesize_conversational_query,
)
from app.agents.reactLoop import run_react_stream
from app.services.knowledge_graph import graph_service as _graph_service
from app.services import vector_service as vs
from app.core.config import settings
from app.services.alarmEvaluation import alarm_direction

logger = logging.getLogger(__name__)


def _is_task_overdue(r: dict[str, Any]) -> bool:
    """Check if task status is explicitly Overdue or scheduled in the past."""
    if r.get("status") == "Overdue":
        return True
    sched = r.get("scheduled_date") or r.get("date")
    if sched and r.get("status") in ("Scheduled", "Pending", "Open"):
        try:
            target_date = datetime.fromisoformat(str(sched).replace("Z", "")).date()
            if target_date < date.today():
                return True
        except Exception:
            pass
    return False


async def _build_maintenance_context(equipment_id: str | None, query: str) -> dict[str, Any]:
    if equipment_id:
        records = await db.get_maintenance_records(equipment_id)
        eq = await db.get_equipment(equipment_id) or {}
    else:
        records = await db.list_all_maintenance_records()
        eq = {}

    overdue: list[dict[str, Any]] = []
    for r in records:
        if _is_task_overdue(r):
            task = dict(r)
            task["status"] = "Overdue"
            overdue.append(task)
    recent = [r for r in records if r.get("status") == "Completed"][:3]

    # Semantic search via Qdrant; keyword search falls back automatically
    similar = await vs.search_similar_incidents(query, equipment_id=equipment_id, limit=4)
    qdrant_active = await vs.is_active()
    similar_degraded = bool(similar.get("degraded", not qdrant_active) if isinstance(similar, dict) else not qdrant_active)
    similar_source = similar.get("source", "qdrant_semantic" if qdrant_active else "keyword_fallback") if isinstance(similar, dict) else ("qdrant_semantic" if qdrant_active else "keyword_fallback")
    similar_items = similar.get("items", list(similar)) if isinstance(similar, dict) else similar

    return {
        "recent_maintenance": recent,
        "overdue_tasks":      overdue,
        "similar_incidents":  similar_items,
        "current_readings":   eq.get("current_readings", {}),
        "health_score":       eq.get("health_score"),
        "failure_probability":eq.get("failure_probability"),
        "vector_search_used": qdrant_active and not similar_degraded,
        "degraded":           similar_degraded,
        "source":             similar_source,
    }


async def _build_compliance_context(equipment_id: str | None) -> dict[str, Any]:
    if equipment_id:
        comp = await db.get_compliance(equipment_id)
        if not comp:
            return {"overall_score": 100, "status": "OK", "issues": [], "passed": []}
    else:
        all_comp = await db.get_all_compliance()
        all_issues = []
        all_passed = []
        for c in all_comp:
            all_issues.extend(c.get("issues") or [])
            all_passed.extend(c.get("passed") or [])
        comp = {"overall_score": 100, "status": "OK", "issues": all_issues, "passed": all_passed}

    issues = comp.get("issues") or []
    if issues:
        sev_penalty = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
        penalty = sum(sev_penalty.get(i.get("severity", "Medium"), 5) for i in issues)
        derived_score = max(0, 100 - penalty)
        derived_status = (
            "Compliant" if derived_score >= 90
            else "Warning" if derived_score >= 75
            else "Non-Compliant" if derived_score >= 50
            else "Critical"
        )
        comp = dict(comp)
        comp["derived_score"] = derived_score
        comp["derived_status"] = derived_status
    return comp


async def _build_lessons_context(query: str, equipment_id: str | None) -> dict[str, Any]:
    # Semantic incident search via Qdrant (falls back to keyword search)
    incidents = await vs.search_similar_incidents(query, equipment_id=equipment_id, limit=5)
    degraded = bool(incidents.get("degraded", False) if isinstance(incidents, dict) else False)
    source = incidents.get("source", "keyword_fallback" if degraded else "qdrant_semantic") if isinstance(incidents, dict) else "unknown"
    inc_items = incidents.get("items", list(incidents)) if isinstance(incidents, dict) else incidents

    lessons = []
    for inc in inc_items:
        if inc.get("lessons_learned"):
            # Similarity only when the retrieval backend actually scored it —
            # no fabricated defaults.
            score = inc.get("_score")
            lessons.append({
                "incident_id": inc.get("incident_id") or inc.get("id"),
                "equipment_id": inc.get("equipment_id") or "PLANT-WIDE",
                "date": inc.get("date"),
                "symptom": inc.get("symptom"),
                "root_cause": inc.get("root_cause"),
                "lesson": inc.get("lessons_learned", ""),
                "similarity": round(score * 100) if isinstance(score, (int, float)) else None,
                "retrieval_source": inc.get("_source", "unknown"),
            })

    return {"lessons": lessons, "pattern_found": len(lessons) > 0, "degraded": degraded, "source": source}


async def _build_documents_context(equipment_id: str | None, query: str) -> dict[str, Any]:
    # Semantic document retrieval via Qdrant; falls back to keyword scan
    qdrant_sections = await vs.search_relevant_docs(query, equipment_id=equipment_id, limit=8)
    degraded = bool(qdrant_sections.get("degraded", False) if isinstance(qdrant_sections, dict) else False)
    source = qdrant_sections.get("source", "keyword_fallback" if degraded else "qdrant_semantic") if isinstance(qdrant_sections, dict) else "unknown"
    sec_items = qdrant_sections.get("items", list(qdrant_sections)) if isinstance(qdrant_sections, dict) else qdrant_sections

    all_docs = await db.get_equipment_documents(equipment_id) if equipment_id else await db.list_all_documents()

    if sec_items:
        # Ensure feedback docs are always included (learning data)
        feedback = [s for s in sec_items if s.get("type") == "feedback"]
        others   = [s for s in sec_items if s.get("type") != "feedback"]
        combined = (feedback + others[:6 - len(feedback)])[:8]
        vector_used = bool(sec_items[0].get("_source", "").startswith("qdrant")) if sec_items else False
        return {
            "relevant_sections":    combined,
            "total_docs_searched":  len(all_docs),
            "feedback_count":       len(feedback),
            "vector_search_used":   vector_used and not degraded,
            "degraded":             degraded,
            "source":               source,
        }

    # Pure PostgreSQL fallback (no Qdrant, no embeddings)
    docs = all_docs
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
        "degraded":            True,
        "source":              "keyword_fallback",
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


async def _run_query_stream_inner(
    equipment_id: str | None = None,
    query: str = "",
    history: list[dict[str, str]] | None = None,
    mode: str | None = None,
) -> AsyncIterator[str]:
    """
    Inner generator yielding SSE-formatted events as each agent completes.
    Each event is:  data: <json>\n\n
    Final event:    data: [DONE]\n\n
    """

    def _event(agent: str, status: str, message: str = "", data: Any = None) -> str:
        payload = {"agent": agent, "status": status, "message": message}
        if data is not None:
            payload["data"] = data
        return f"data: {json.dumps(payload)}\n\n"

    # ── Deterministic equipment resolution before fan-out (WP-2) ────────────
    resolution = await resolve_equipment(query=query, equipment_id=equipment_id)

    if resolution.is_ambiguous:
        candidates_str = ", ".join(resolution.candidates)
        yield _event(
            "equipment_brain",
            "done",
            f"Ambiguous query: matches {len(resolution.candidates)} equipment tags ({candidates_str}).",
            data={"ambiguous": True, "candidates": resolution.candidates},
        )
        yield _event(
            "synthesizer",
            "done",
            f"Query matches multiple equipment ({candidates_str}). Please clarify your target asset.",
            data={
                "response_type": "chat",
                "message": (
                    f"Your inquiry matches multiple assets in the plant: **{candidates_str}**.\n\n"
                    "Please specify which equipment you would like to inspect."
                ),
                "ambiguous": True,
                "candidates": resolution.candidates,
                "risk_level": "Unknown",
                "risk_summary": f"Ambiguous query matching: {candidates_str}",
            },
        )
        yield "data: [DONE]\n\n"
        return

    target_equipment_id = resolution.equipment_id if resolution.is_resolved else None
    resolved_name = resolution.equipment_name

    # ── 1-5. Specialist retrievers — run concurrently ─────────────────────────

    async def _equipment_brain() -> tuple[dict, dict]:
        if target_equipment_id:
            brain = await _graph_service.get_equipment_brain(target_equipment_id)
            eq = await db.get_equipment(target_equipment_id) or {}
            readings = eq.get("current_readings") or {}
            vib_de = readings.get("vibration_de", {}) if isinstance(readings, dict) else {}
            summary = {
                "name": eq.get("name"),
                "type": eq.get("type"),
                "health_score": eq.get("health_score"),
                "failure_probability": eq.get("failure_probability"),
                "current_vibration": vib_de.get("value"),
                "alarm_threshold": vib_de.get("alarm"),
                "alarm_direction": alarm_direction(vib_de),
                "maintenance_due_days": eq.get("maintenance_due_days"),
                "incident_count": len(await db.get_equipment_incidents(target_equipment_id)),
                "connected_equipment": eq.get("downstream_equipment") or [],
                "technicians": eq.get("technicians") or [],
                "source": "postgres_graph",
                "resolved_equipment_id": target_equipment_id,
            }
            summary["highlights"] = _build_highlights("equipment_brain", query, summary)
            return brain, summary
        else:
            all_eq = await db.get_all_equipment_list()
            scores = [e.get("health_score") for e in all_eq if e.get("health_score") is not None]
            fail_probs = [e.get("failure_probability") for e in all_eq if e.get("failure_probability") is not None]
            avg_health = round(sum(scores) / len(scores), 1) if scores else 100.0
            avg_fail = round(sum(fail_probs) / len(fail_probs), 2) if fail_probs else 0.0
            due_days = [e.get("maintenance_due_days") for e in all_eq if e.get("maintenance_due_days") is not None]
            min_due = min(due_days) if due_days else None

            summary = {
                "name": "Plant-wide Overview",
                "type": "All Equipment",
                "health_score": avg_health,
                "failure_probability": avg_fail,
                "current_vibration": None,
                "alarm_threshold": None,
                "maintenance_due_days": min_due,
                "incident_count": 0,
                "connected_equipment": [e.get("id") for e in all_eq if e.get("id")],
                "technicians": [],
                "source": "postgres_graph",
                "scope": "plant_wide",
                "resolved_equipment_id": None,
            }
            summary["highlights"] = _build_highlights("equipment_brain", query, summary)
            brain = {
                "equipment": {"id": "PLANT-WIDE", "name": "Plant-wide Overview", "type": "All Equipment"},
                "all_equipment": all_eq,
                "total_assets": len(all_eq),
            }
            return brain, summary

    # Echo resolved asset in first SSE event (WP-2 guardrail)
    if target_equipment_id:
        first_brain_msg = (
            f"Target asset: {target_equipment_id}"
            + (f" ({resolved_name})" if resolved_name else "")
            + " — Loading equipment memory from knowledge graph…"
        )
        first_brain_data = {
            "resolved_equipment_id": target_equipment_id,
            "resolved_equipment_name": resolved_name,
            "scope": "asset",
        }
    else:
        first_brain_msg = "Plant-wide scope — Loading plant-wide asset overview…"
        first_brain_data = {
            "resolved_equipment_id": None,
            "scope": "plant_wide",
        }

    yield _event("equipment_brain", "active", first_brain_msg, data=first_brain_data)

    # ── 3-Way Query Routing (WP-4) ──────────────────────────────────────────
    route = (mode or "").lower() or classify_query_intent(query)

    if route == "conversational":
        yield _event("synthesizer", "active", "Generating conversational response…")
        resp = await synthesize_conversational_query(query=query, history=history)
        yield _event("synthesizer", "done", "Response ready", resp)
        yield "data: [DONE]\n\n"
        return

    if route in ("multi_hop", "react"):
        async for react_event in run_react_stream(
            equipment_id=target_equipment_id,
            query=query,
            history=history,
        ):
            yield react_event
        return

    # ── Standard diagnostic: preserve 5-way parallel asyncio.gather fan-out ──
    for agent, msg in (
        ("maintenance_advisor", "Searching maintenance history and similar incidents…"),
        ("compliance_agent", "Reading the stored compliance record and open issues…"),
        ("lessons_learned", "Scanning historical incidents for matching failure patterns…"),
        ("document_intelligence", "Searching OEM manuals, SOPs, and safety standards…"),
    ):
        yield _event(agent, "active", msg)

    (brain, brain_summary), maintenance_ctx, compliance_ctx, lessons_ctx, docs_ctx = \
        await asyncio.gather(
            _equipment_brain(),
            _build_maintenance_context(target_equipment_id, query),
            _build_compliance_context(target_equipment_id),
            _build_lessons_context(query, target_equipment_id),
            _build_documents_context(target_equipment_id, query),
        )

    yield _event("equipment_brain", "done", "Equipment memory loaded", brain_summary)

    maintenance_ctx["highlights"] = _build_highlights("maintenance_advisor", query, maintenance_ctx)
    yield _event(
        "maintenance_advisor",
        "done",
        f"Found {len(maintenance_ctx['overdue_tasks'])} overdue task(s), {len(maintenance_ctx['similar_incidents'])} similar incident(s)",
        maintenance_ctx,
    )

    issue_count = len(compliance_ctx.get("issues") or [])
    high_issues = len([i for i in (compliance_ctx.get("issues") or []) if i.get("severity") == "High"])
    compliance_ctx["highlights"] = _build_highlights("compliance_agent", query, compliance_ctx)
    yield _event(
        "compliance_agent",
        "done",
        f"{issue_count} compliance issue(s) found ({high_issues} High severity)",
        compliance_ctx,
    )

    match_count = len(lessons_ctx.get("lessons", []))
    lessons_ctx["highlights"] = _build_highlights("lessons_learned", query, lessons_ctx)
    yield _event(
        "lessons_learned",
        "done",
        (f"Pattern match found — {match_count} historical incident(s) with similar signature"
         if match_count else "No matching historical failure patterns found"),
        lessons_ctx,
    )

    docs_ctx["highlights"] = _build_highlights("document_intelligence", query, docs_ctx)
    yield _event(
        "document_intelligence",
        "done",
        f"Retrieved {len(docs_ctx['relevant_sections'])} relevant document sections from {docs_ctx['total_docs_searched']} documents"
        + (f" (incl. {docs_ctx['feedback_count']} real-world feedback records)" if docs_ctx.get("feedback_count") else ""),
        docs_ctx,
    )

    # ── 6. Synthesizer (GPT-4.1) ──────────────────────────────────────────────
    yield _event("synthesizer", "active", f"Synthesizing final recommendation with {settings.openai_model}…")
    final = await synthesize_query(
        equipment_id=target_equipment_id or "All Equipment (Plant-wide)",
        query=query,
        equipment_context=brain,
        maintenance_context=maintenance_ctx,
        compliance_context=compliance_ctx,
        lessons_context=lessons_ctx,
        documents_context=docs_ctx,
        history=history or [],
    )
    is_degraded = bool(
        maintenance_ctx.get("degraded")
        or docs_ctx.get("degraded")
        or lessons_ctx.get("degraded")
    )
    if isinstance(final, dict):
        final["degraded"] = is_degraded
        if is_degraded:
            final["source"] = "keyword_fallback"
            final["degraded_reason"] = "Operating in degraded fallback mode (vector search degraded; keyword retrieval used)"
    yield _event("synthesizer", "done", "Analysis complete", final)

    yield "data: [DONE]\n\n"


async def run_query_stream(
    equipment_id: str | None = None,
    query: str = "",
    history: list[dict[str, str]] | None = None,
    mode: str | None = None,
) -> AsyncIterator[str]:
    """
    Yield SSE-formatted events as each agent completes.
    Guarantees [DONE] is always emitted, and yields an error event if an exception occurs.
    """
    done_emitted = False
    try:
        async for chunk in _run_query_stream_inner(equipment_id, query, history, mode):
            if chunk == "data: [DONE]\n\n":
                done_emitted = True
            yield chunk
    except Exception as exc:
        logger.error("run_query_stream failed: %s", exc, exc_info=True)
        payload = {"agent": "orchestrator", "status": "error", "message": f"Query failed: {str(exc)}", "data": {"error": str(exc)}}
        yield f"data: {json.dumps(payload)}\n\n"
    finally:
        if not done_emitted:
            yield "data: [DONE]\n\n"

