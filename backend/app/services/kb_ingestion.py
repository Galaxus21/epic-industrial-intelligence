"""
AI Operations Brain — Knowledge Base Ingestion Service
Central hub that routes every operational event into the knowledge graph,
document store, and incident/maintenance tables so AI agents always query
the freshest data.

Every public function is fire-and-forget safe:
  - called with `asyncio.create_task()` at endpoint call sites
  - failures are caught and logged, never propagated to the caller

Events handled:
  on_work_order_created    — adds graph node + pending maintenance record
  on_work_order_completed  — enriches document, creates lessons-learned incident
  on_checklist_created     — adds graph node
  on_checklist_completed   — document + maintenance record with outcomes
  on_safety_conflict       — logs PTW/HAZOP conflict as incident + document
  on_form_submission       — routes defect/incident/WO submissions to KB
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from app.services import db_service as db
from app.services.audit import audit

logger = logging.getLogger(__name__)

_TODAY = lambda: datetime.utcnow().strftime("%Y-%m-%d")   # noqa: E731
_NOW   = lambda: datetime.utcnow().isoformat()             # noqa: E731


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _save_kb_document(doc_id: str, name: str, equipment_id: str,
                             doc_type: str, sections: dict[str, str],
                             summary: str, extra_equipment: list[str] | None = None) -> None:
    """Persist a processed document to the knowledge base."""
    equipment_ids = list({equipment_id} | set(extra_equipment or []))
    await db.save_document({
        "id": doc_id,
        "name": name,
        "type": doc_type,
        "equipment_ids": equipment_ids,
        "date": _TODAY(),
        "status": "processed",
        "sections": sections,
        "entities": {
            "equipment_ids": equipment_ids,
            "document_type": doc_type,
            "summary": summary,
        },
        "pipeline_steps": {s: "done" for s in ["saved", "extracted", "entities", "graph", "indexed"]},
        "current_step": "done",
    })


async def _add_kb_node(node_id: str, label: str, node_type: str,
                        equipment_id: str, relation: str, val: int = 12) -> None:
    """Add a knowledge graph node and link it to its equipment."""
    await db.upsert_graph_node({"id": node_id, "name": label, "type": node_type, "val": val})
    try:
        await db.add_graph_link(equipment_id, node_id, relation)
    except Exception:
        pass  # equipment node might not exist yet for discovered equipment


# ─────────────────────────────────────────────────────────────────────────────
# Work Order events
# ─────────────────────────────────────────────────────────────────────────────

async def on_work_order_created(
    wo_id: str,
    equipment_id: str,
    wo_type: str,
    description: str,
    risk_level: str | None,
    spare_parts: list[str],
    safety_precautions: list[str],
    required_permits: list[str],
) -> None:
    """Called when a new work order is created (by AI query, form, or threshold monitor)."""
    try:
        # 1. Graph node for the WO
        label = f"WO\n{wo_type}\n{equipment_id}"
        await _add_kb_node(wo_id, label, "work_order", equipment_id, "HAS_WORK_ORDER", val=14)

        # Audit log
        audit("create", "work_order", wo_id, equipment_id=equipment_id,
              actor="system", notes=f"WO created: {description[:80]}",
              risk_level=risk_level,
              changes={"wo_type": wo_type, "spare_parts": spare_parts, "permits": required_permits})

        # 2. Pending maintenance record so agents see the WO in maintenance history
        await db.upsert_maintenance_record({
            "id": f"MR-{wo_id}",
            "equipment_id": equipment_id,
            "date": _TODAY(),
            "type": wo_type,
            "description": f"Work Order Created: {description}",
            "status": "Scheduled",
            "findings": f"WO {wo_id} opened. Risk: {risk_level or 'Unknown'}. "
                        f"Permits: {', '.join(required_permits) or 'None'}. "
                        f"Spare parts: {', '.join(spare_parts) or 'None'}.",
        })

        # 3. Light document so Document Intelligence agent can reference it
        await _save_kb_document(
            doc_id=f"DOC-{wo_id}",
            name=f"Work Order {wo_id}: {wo_type} on {equipment_id}",
            equipment_id=equipment_id,
            doc_type="work_order",
            sections={"description": description,
                      "risk_level": risk_level or "Unknown",
                      "spare_parts": ", ".join(spare_parts) or "None",
                      "safety_precautions": "\n".join(safety_precautions) or "None",
                      "required_permits": "\n".join(required_permits) or "None"},
            summary=f"Work order '{wo_type}' opened for {equipment_id}: {description}",
        )

        logger.info("KB: work order created → %s for %s", wo_id, equipment_id)
    except Exception as exc:
        logger.error("KB ingest error on_work_order_created %s: %s", wo_id, exc)


async def on_work_order_completed(
    wo_id: str,
    equipment_id: str,
    wo_type: str,
    description: str,
    risk_level: str | None,
    solution_worked: bool | None,
    outcome_notes: str | None,
    extra_steps_taken: str | None,
    completed_by: str | None,
    actual_duration_hours: float | None,
    steps: list[dict[str, Any]],
    spare_parts: list[str],
) -> None:
    """Called when a work order is marked complete. Enriches KB with outcome knowledge."""
    try:
        worked_str = "YES" if solution_worked else ("NO" if solution_worked is False else "UNKNOWN")
        completed_steps = [s for s in steps if s.get("checked")]
        n_steps = len(steps)

        # 1. Outcome document (replaces/updates the earlier creation document)
        doc_id = f"FEEDBACK-{wo_id[:8].upper()}"
        sections: dict[str, str] = {
            "description": description,
            "solution_effective": f"Solution worked: {worked_str}",
        }
        if outcome_notes:     sections["outcome"]      = outcome_notes
        if extra_steps_taken: sections["extra_steps"]  = extra_steps_taken
        if completed_by:      sections["completed_by"] = completed_by
        if actual_duration_hours:
            sections["duration"] = f"{actual_duration_hours}h (estimated {steps[0].get('expected_duration_minutes', '?')}min per step)"
        if completed_steps:
            sections["steps_executed"] = "\n".join(
                f"Step {s['step']}: {s['title']} — {s.get('actual_notes', '').strip() or 'completed'}"
                for s in completed_steps
            )

        await _save_kb_document(
            doc_id=doc_id,
            name=f"Work Order Outcome: {wo_type} on {equipment_id} ({_TODAY()})",
            equipment_id=equipment_id,
            doc_type="feedback",
            sections=sections,
            summary=(
                f"Work order '{wo_type}' for {equipment_id} completed. "
                f"Solution worked: {worked_str}. "
                f"{len(completed_steps)}/{n_steps} steps executed. "
                f"{outcome_notes or ''}"
            ),
        )
        await _add_kb_node(doc_id, f"Outcome\n{equipment_id}\n{worked_str}", "feedback", equipment_id, "HAS_FEEDBACK", val=12)

        # Audit log
        audit("complete", "work_order", wo_id, equipment_id=equipment_id,
              actor=completed_by or "system", notes=outcome_notes,
              risk_level=risk_level,
              changes={"solution_worked": worked_str, "duration_h": actual_duration_hours,
                       "steps_done": len(completed_steps), "steps_total": n_steps})

        # 2. Completed maintenance record (so it shows in maintenance history tab)
        findings_parts = [f"WO {wo_id} completed. Solution: {worked_str}."]
        if outcome_notes:     findings_parts.append(outcome_notes)
        if extra_steps_taken: findings_parts.append(f"Extra steps: {extra_steps_taken}")
        if completed_by:      findings_parts.append(f"Completed by: {completed_by}")

        await db.upsert_maintenance_record({
            "id": f"MR-DONE-{wo_id[:8]}",
            "equipment_id": equipment_id,
            "date": _TODAY(),
            "type": wo_type,
            "description": f"Work Order Completed: {description}",
            "status": "Completed",
            "findings": " ".join(findings_parts),
            "technician": completed_by,
        })

        # 3. Lessons-learned incident record when outcome reveals useful knowledge
        if outcome_notes or (solution_worked is False) or extra_steps_taken:
            severity = "Medium" if solution_worked else "High"
            lesson_text = " | ".join(filter(None, [outcome_notes, extra_steps_taken]))
            await db.upsert_incident({
                "id": f"LESSON-{wo_id[:8]}",
                "equipment_id": equipment_id,
                "date": _TODAY(),
                "title": f"Lessons Learned — WO {wo_id[:8]}: {wo_type}",
                "severity": severity,
                "symptom": description,
                "root_cause": f"Work order type: {wo_type}",
                "action_taken": f"Solution worked: {worked_str}. {lesson_text}",
                "lessons_learned": lesson_text or f"Completed {len(completed_steps)}/{n_steps} steps.",
                "technician": completed_by,
                "keywords": list({
                    wo_type.lower(), equipment_id.lower(),
                    *[w for w in (description + " " + (outcome_notes or "")).lower().split()
                      if len(w) > 4]
                })[:15],
            })
            await _add_kb_node(
                f"LESSON-{wo_id[:8]}", f"Lessons\n{equipment_id}",
                "lesson", equipment_id, "HAS_LESSON", val=10,
            )

        logger.info("KB: work order completed → %s (%s, worked=%s)", wo_id, equipment_id, solution_worked)
    except Exception as exc:
        logger.error("KB ingest error on_work_order_completed %s: %s", wo_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Checklist events
# ─────────────────────────────────────────────────────────────────────────────

async def on_checklist_created(
    cl_id: str,
    equipment_id: str,
    risk_level: str | None,
    items: list[str],
) -> None:
    """Called when an inspection checklist is created."""
    try:
        await _add_kb_node(cl_id, f"Checklist\n{equipment_id}\n{risk_level or ''}", "checklist", equipment_id, "HAS_CHECKLIST", val=10)
        audit("create", "checklist", cl_id, equipment_id=equipment_id,
              actor="system", notes=f"{len(items)} inspection items", risk_level=risk_level)
        logger.info("KB: checklist created → %s for %s (%d items)", cl_id, equipment_id, len(items))
    except Exception as exc:
        logger.error("KB ingest error on_checklist_created %s: %s", cl_id, exc)


async def on_checklist_completed(
    cl_id: str,
    equipment_id: str,
    risk_level: str | None,
    items: list[dict[str, Any]],
    outcome_notes: str | None,
) -> None:
    """Called when an inspection checklist is completed. Ingests findings into KB."""
    try:
        checked   = [it for it in items if it.get("checked")]
        unchecked = [it for it in items if not it.get("checked")]
        n         = len(items)

        # Build readable sections
        sections: dict[str, str] = {
            "summary": f"Inspection checklist {cl_id} for {equipment_id}. {len(checked)}/{n} items completed.",
            "items_completed": "\n".join(
                f"✓ {it['text']}" + (f" — {it['notes']}" if it.get("notes") else "")
                for it in checked
            ) or "None",
        }
        if unchecked:
            sections["items_pending"] = "\n".join(f"○ {it['text']}" for it in unchecked)
        if outcome_notes:
            sections["outcome"] = outcome_notes

        doc_id = f"INSP-{cl_id[:8].upper()}"
        await _save_kb_document(
            doc_id=doc_id,
            name=f"Inspection Report: {equipment_id} — {_TODAY()} ({risk_level or 'N/A'} Risk)",
            equipment_id=equipment_id,
            doc_type="inspection_report",
            sections=sections,
            summary=(
                f"Inspection of {equipment_id} completed. {len(checked)}/{n} items OK. "
                f"Risk: {risk_level or 'N/A'}. {outcome_notes or ''}"
            ),
        )

        # Completed maintenance record (checklist = inspection)
        findings = f"{len(checked)}/{n} items passed."
        if unchecked: findings += f" Pending: {'; '.join(it['text'] for it in unchecked[:3])}."
        if outcome_notes: findings += f" Notes: {outcome_notes}"

        await db.upsert_maintenance_record({
            "id": f"MR-CL-{cl_id[:8]}",
            "equipment_id": equipment_id,
            "date": _TODAY(),
            "type": "Inspection",
            "description": f"Inspection Checklist Completed: {cl_id}",
            "status": "Completed",
            "findings": findings,
        })

        # Update graph node
        await _add_kb_node(doc_id, f"Inspection\n{equipment_id}\n{_TODAY()}", "inspection_report", equipment_id, "HAS_INSPECTION", val=11)
        audit("complete", "checklist", cl_id, equipment_id=equipment_id,
              actor="system", notes=findings, risk_level=risk_level,
              changes={"items_passed": len(checked), "items_total": n})

        logger.info("KB: checklist completed → %s for %s (%d/%d items)", cl_id, equipment_id, len(checked), n)
    except Exception as exc:
        logger.error("KB ingest error on_checklist_completed %s: %s", cl_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Safety / PTW events
# ─────────────────────────────────────────────────────────────────────────────

async def on_safety_conflict(
    equipment_id: str,
    action: str,
    conflicts: list[dict[str, Any]],
    hazop_notes: list[str],
    clearance: str,
    required_permits: list[str],
) -> None:
    """
    Called when a PTW conflict check is run.
    If conflicts were found, persists a safety record so the AI
    can warn engineers in future queries about known conflicts on this equipment.
    """
    if not conflicts and clearance == "CLEAR":
        return   # no-op for clean checks — no KB pollution

    try:
        record_id  = f"PTW-{uuid.uuid4().hex[:8].upper()}"
        severity   = "Critical" if clearance == "BLOCKED" else "High"
        conflict_summary = "; ".join(
            f"{c['permit_type']} ({c['permit_id']}): {c['conflict_reason'][:80]}"
            for c in conflicts
        ) if conflicts else "No permit conflicts."

        # Incident record — so Lessons Learned agent surfaces it
        await db.upsert_incident({
            "id": record_id,
            "equipment_id": equipment_id,
            "date": _TODAY(),
            "title": f"Safety Check — PTW Conflict ({clearance}): {action[:60]}",
            "severity": severity,
            "symptom": f"Proposed action: {action}",
            "root_cause": "Permit-to-Work or HAZOP conflict detected",
            "action_taken": (
                f"Clearance: {clearance}. Conflicts: {conflict_summary}. "
                f"Required permits: {', '.join(required_permits) or 'None'}. "
                f"HAZOP notes: {'; '.join(hazop_notes[:2]) or 'None'}."
            ),
            "lessons_learned": (
                f"When planning '{action}' on {equipment_id}, verify: "
                f"{', '.join(c['permit_type'] for c in conflicts)}. "
                f"Clearance was {clearance}."
            ),
            "keywords": [
                "ptw", "permit", "safety", "conflict", equipment_id.lower(),
                *action.lower().split()[:4],
            ],
        })

        # Document record — for Document Intelligence agent
        await _save_kb_document(
            doc_id=f"DOC-{record_id}",
            name=f"Safety Check: {action[:50]} on {equipment_id} ({_TODAY()})",
            equipment_id=equipment_id,
            doc_type="safety_check",
            sections={
                "action": action,
                "clearance": clearance,
                "conflicts": conflict_summary,
                "hazop_notes": "\n".join(hazop_notes) or "None",
                "required_permits": "\n".join(required_permits) or "None",
            },
            summary=f"Safety check for '{action}' on {equipment_id}: {clearance}. {conflict_summary}",
        )

        # Graph node
        await _add_kb_node(record_id, f"Safety\n{clearance}\n{equipment_id}", "safety_check", equipment_id, "HAS_SAFETY_CHECK", val=11)
        audit("check", "safety", record_id, equipment_id=equipment_id,
              actor="system", notes=f"Action: {action[:80]}",
              risk_level="Critical" if clearance == "BLOCKED" else "High",
              changes={"clearance": clearance, "conflicts": len(conflicts), "action": action})

        logger.info("KB: safety conflict logged → %s for %s (clearance=%s)", record_id, equipment_id, clearance)
    except Exception as exc:
        logger.error("KB ingest error on_safety_conflict %s: %s", equipment_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Form submission events
# ─────────────────────────────────────────────────────────────────────────────

async def on_form_submission(
    form_type: str,
    equipment_id: str,
    record_id: str,
    field_values: dict[str, Any],
) -> None:
    """
    Called after any form is submitted.
    Adds graph nodes and document records for incident/defect/work_order forms.
    Sensor logs and maintenance records are already handled by db_service.
    """
    try:
        if form_type in ("incident_report", "defect_report"):
            title = field_values.get("title") or field_values.get("defect_type") or form_type.replace("_", " ").title()
            severity = field_values.get("severity", "Medium")
            description = field_values.get("description") or field_values.get("symptom") or ""
            location = field_values.get("location_on_equipment", "")

            node_label = f"{form_type.split('_')[0].title()}\n{equipment_id}\n{severity}"
            await _add_kb_node(record_id, node_label, form_type, equipment_id, "HAS_INCIDENT", val=13)
            audit("submit", form_type, record_id, equipment_id=equipment_id,
                  actor="user", actor_type="user", notes=description[:100],
                  risk_level=severity)

            # Document record for Document Intelligence
            sections: dict[str, str] = {
                "type": form_type.replace("_", " ").title(),
                "severity": severity,
                "description": description,
            }
            if location: sections["location"] = location
            if field_values.get("root_cause"):   sections["root_cause"]   = field_values["root_cause"]
            if field_values.get("action_taken"): sections["action_taken"] = field_values["action_taken"]

            await _save_kb_document(
                doc_id=f"DOC-{record_id}",
                name=f"{title} — {equipment_id} ({_TODAY()})",
                equipment_id=equipment_id,
                doc_type=form_type,
                sections=sections,
                summary=f"{form_type.replace('_', ' ').title()} on {equipment_id}: {description[:150]}",
            )
            logger.info("KB: %s form ingested → %s for %s", form_type, record_id, equipment_id)

        elif form_type == "work_order":
            wo_type  = field_values.get("wo_type", "Corrective")
            priority = field_values.get("priority", "High")
            desc     = field_values.get("description", "")
            await _add_kb_node(record_id, f"WO\n{wo_type}\n{equipment_id}", "work_order", equipment_id, "HAS_WORK_ORDER", val=14)
            await _save_kb_document(
                doc_id=f"DOC-{record_id}",
                name=f"Work Order (Form): {wo_type} on {equipment_id} ({_TODAY()})",
                equipment_id=equipment_id,
                doc_type="work_order",
                sections={"wo_type": wo_type, "priority": priority, "description": desc},
                summary=f"Work order '{wo_type}' raised for {equipment_id}: {desc[:150]}",
            )
            logger.info("KB: work_order form ingested → %s for %s", record_id, equipment_id)

        # sensor_log and maintenance_record are already persisted via db_service.upsert_maintenance_record
        # equipment_reg is handled via db_service.upsert_equipment + upsert_graph_node in forms.py

    except Exception as exc:
        logger.error("KB ingest error on_form_submission %s/%s: %s", form_type, record_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: fire-and-forget wrapper
# ─────────────────────────────────────────────────────────────────────────────

def ingest_async(coro) -> None:
    """Schedule a KB ingestion coroutine as a background task (best-effort)."""
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        # No running event loop (e.g. in tests) — run synchronously
        asyncio.get_event_loop().run_until_complete(coro)
