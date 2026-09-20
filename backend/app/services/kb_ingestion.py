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
"""
from __future__ import annotations

import asyncio
import logging
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
    except (KeyError, ValueError) as exc:
        logger.warning("Equipment %s not ready for graph link %s (%s): %s", equipment_id, node_id, relation, exc)
    except Exception as exc:
        logger.warning("Graph link failed %s->%s (%s): %s", equipment_id, node_id, relation, exc, exc_info=True)


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
    actor: str = "system",
) -> None:
    """Called when a new work order is created (by AI query, form, or threshold monitor)."""
    try:
        # 1. Graph node for the WO
        label = f"WO\n{wo_type}\n{equipment_id}"
        await _add_kb_node(wo_id, label, "work_order", equipment_id, "HAS_WORK_ORDER", val=14)

        # Audit log
        actor_type = "user" if actor and actor not in ("system", "threshold_monitor") else "system"
        audit("create", "work_order", wo_id, equipment_id=equipment_id,
              actor=actor or "system", actor_type=actor_type, notes=f"WO created: {description[:80]}",
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
        doc_id = f"FEEDBACK-{wo_id.upper()}"
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
        actor_type = "user" if completed_by and completed_by != "system" else "system"
        audit("complete", "work_order", wo_id, equipment_id=equipment_id,
              actor=completed_by or "system", notes=outcome_notes,
              risk_level=risk_level, actor_type=actor_type,
              changes={"solution_worked": worked_str, "duration_h": actual_duration_hours,
                       "steps_done": len(completed_steps), "steps_total": n_steps})

        # 2. Completed maintenance record (so it shows in maintenance history tab)
        findings_parts = [f"WO {wo_id} completed. Solution: {worked_str}."]
        if outcome_notes:     findings_parts.append(outcome_notes)
        if extra_steps_taken: findings_parts.append(f"Extra steps: {extra_steps_taken}")
        if completed_by:      findings_parts.append(f"Completed by: {completed_by}")

        await db.upsert_maintenance_record({
            "id": f"MR-DONE-{wo_id}",
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
                "id": f"LESSON-{wo_id}",
                "equipment_id": equipment_id,
                "date": _TODAY(),
                "title": f"Lessons Learned — WO {wo_id}: {wo_type}",
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
                f"LESSON-{wo_id}", f"Lessons\n{equipment_id}",
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
# Convenience: fire-and-forget wrapper
# ─────────────────────────────────────────────────────────────────────────────

_ingest_tasks: set[asyncio.Task] = set()


def get_ingest_tasks() -> set[asyncio.Task]:
    """Return currently tracked background ingestion tasks."""
    return set(_ingest_tasks)


def ingest_async(coro) -> asyncio.Task | None:
    """Schedule a KB ingestion coroutine as a tracked background task (best-effort).

    Eliminates nested event loops (run_until_complete) and retains tasks against
    premature garbage collection via _ingest_tasks and done callbacks.
    """
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(coro)
        _ingest_tasks.add(task)
        task.add_done_callback(_ingest_tasks.discard)
        return task
    except RuntimeError:
        # No running event loop (e.g. outside async context)
        try:
            asyncio.run(coro)
        except Exception as exc:
            logger.warning("Failed to execute ingest_async outside event loop: %s", exc, exc_info=True)
        return None
