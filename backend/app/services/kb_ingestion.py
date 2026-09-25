"""
AI Operations Brain — Knowledge Base Ingestion Service
Central hub that routes every operational event into the knowledge graph,
document store, and incident/maintenance tables so AI agents always query
the freshest data.

on_work_order_created and on_work_order_completed are fire-and-forget safe: called through ingest_async at endpoint
call sites, their failures are caught and logged, never propagated to the caller. on_work_order_deleted is awaited
before the row is deleted and lets errors propagate, so a failed cleanup keeps the work order for a retry.

Events handled:
  on_work_order_created    — adds graph node + the work order's Scheduled maintenance record
  on_work_order_completed  — outcome document, the same maintenance record marked Completed, lessons-learned incident
  on_work_order_deleted    — removes the creation document and graph node, cancels a record still Scheduled
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.services import db_service as db
from app.services.audit import audit
from app.services.incidentWriter import saveIncident

logger = logging.getLogger(__name__)

_TODAY = lambda: datetime.utcnow().strftime("%Y-%m-%d")   # noqa: E731

# Documents the app writes itself (work-order outcomes, lessons, saved AI drafts) go to the
# database only, never through the vector index, and their pipeline card says so.
appWrittenPipelineSteps = {"saved": "done", "extracted": "done", "entities": "done", "graph": "done", "indexed": "skipped"}
CANCELLED_STATUS = "Cancelled"


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
        "pipeline_steps": dict(appWrittenPipelineSteps),
        "current_step": "done",
    })


def workOrderRecordId(wo_id: str) -> str:
    """The one maintenance record a work order has: Scheduled when saved, Completed or Cancelled later."""
    return f"MR-{wo_id}"


def _estimateNote(steps: list[dict[str, Any]]) -> str:
    estimates = [step["expected_duration_minutes"] for step in steps
                 if isinstance(step.get("expected_duration_minutes"), (int, float))]
    return f" (estimated {sum(estimates)} min over {len(estimates)} steps)" if estimates else ""


def outcomeLabel(solution_worked: bool | None, is_partial: bool) -> str:
    if is_partial:
        return "PARTIAL"
    if solution_worked is None:
        return "UNKNOWN"
    return "YES" if solution_worked else "NO"


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
    """Called when a user saves a new work order (POST /api/v1/work-orders). The threshold monitor writes its own
    work orders and audit rows and does not call this."""
    try:
        # 1. Graph node for the WO
        label = f"{wo_id}\n{wo_type} work order on {equipment_id}"
        await _add_kb_node(wo_id, label, "work_order", equipment_id, "HAS_WORK_ORDER", val=14)

        # Audit log
        actor_type = "user" if actor and actor not in ("system", "threshold_monitor") else "system"
        audit("create", "work_order", wo_id, equipment_id=equipment_id,
              actor=actor or "system", actor_type=actor_type, notes=f"WO created: {description[:80]}",
              risk_level=risk_level,
              changes={"wo_type": wo_type, "spare_parts": spare_parts, "permits": required_permits})

        # 2. Pending maintenance record so agents see the WO in maintenance history
        await db.upsert_maintenance_record({
            "id": workOrderRecordId(wo_id),
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
    is_partial: bool,
    outcome_notes: str | None,
    extra_steps_taken: str | None,
    completed_by: str | None,
    actual_duration_hours: float | None,
    steps: list[dict[str, Any]],
    spare_parts: list[str],
) -> None:
    """Called when a work order is marked complete. Enriches KB with outcome knowledge."""
    try:
        worked_str = outcomeLabel(solution_worked, is_partial)
        completed_steps = [s for s in steps if s.get("checked")]
        n_steps = len(steps)

        # 1. Outcome document, beside the creation document DOC-<id> (which records what was planned)
        doc_id = f"FEEDBACK-{wo_id.upper()}"
        sections: dict[str, str] = {
            "description": description,
            "solution_effective": f"Solution worked: {worked_str}",
        }
        if outcome_notes:     sections["outcome"]      = outcome_notes
        if extra_steps_taken: sections["extra_steps"]  = extra_steps_taken
        if completed_by:      sections["completed_by"] = completed_by
        if actual_duration_hours:
            sections["duration"] = f"{actual_duration_hours}h actual" + _estimateNote(steps)
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
        await _add_kb_node(doc_id, f"Outcome of {wo_id}\nSolution worked: {worked_str}", "feedback", equipment_id,
                           "HAS_FEEDBACK", val=12)

        # Audit log
        actor_type = "user" if completed_by and completed_by != "system" else "system"
        audit("complete", "work_order", wo_id, equipment_id=equipment_id,
              actor=completed_by or "system", notes=outcome_notes,
              risk_level=risk_level, actor_type=actor_type,
              changes={"solution_worked": worked_str, "duration_h": actual_duration_hours,
                       "steps_done": len(completed_steps), "steps_total": n_steps})

        # 2. The work order's maintenance record, written as Scheduled when it was saved, now records the completed
        #    job: one record per work order, so a finished job is never also counted as overdue scheduled work.
        findings_parts = [f"WO {wo_id} completed. Solution: {worked_str}."]
        if outcome_notes:     findings_parts.append(outcome_notes)
        if extra_steps_taken: findings_parts.append(f"Extra steps: {extra_steps_taken}")
        if completed_by:      findings_parts.append(f"Completed by: {completed_by}")

        await db.upsert_maintenance_record({
            "id": workOrderRecordId(wo_id),
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
            await saveIncident({
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
                f"LESSON-{wo_id}", f"Lesson from {wo_id}\n{equipment_id}",
                "lesson", equipment_id, "HAS_LESSON", val=10,
            )

        logger.info("KB: work order completed → %s (%s, worked=%s)", wo_id, equipment_id, solution_worked)
    except Exception as exc:
        logger.error("KB ingest error on_work_order_completed %s: %s", wo_id, exc)


async def on_work_order_deleted(wo_id: str, equipment_id: str, completed: bool) -> None:
    """Called before a work order row is deleted. What described it as open work goes: its creation document and graph
    node, and its maintenance record is marked Cancelled rather than left Scheduled to turn overdue. A completed job's
    record, outcome document and lesson stay as history. Errors propagate, so the work order is kept for a retry."""
    await db.delete_document(f"DOC-{wo_id}")
    await db.remove_graph_node_and_links(wo_id)
    if completed:
        return
    recordId = workOrderRecordId(wo_id)
    if any(record["id"] == recordId for record in await db.get_maintenance_records(equipment_id)):
        await db.upsert_maintenance_record({"id": recordId, "status": CANCELLED_STATUS,
                                            "findings": f"WO {wo_id} deleted before completion."})


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
