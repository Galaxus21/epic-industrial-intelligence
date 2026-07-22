"""
AI Operations Brain — Slack Message Ingestor
Classifies incoming Slack messages and persists them into the appropriate
DB tables so they are visible on the dashboard and included in AI context.

Principle: every data ingestion stores in BOTH the relational DB AND the
knowledge base (Qdrant vector store) so the AI agent pipeline can retrieve
communications alongside documents, incidents, and maintenance records.

AI-powered pipeline (when OPENAI_API_KEY is set):
  1. LLM reads the full Slack message and extracts:
       classification, equipment IDs, severity, title, summary,
       action required, estimated duration, technician, root cause hint,
       type-specific fields for the target form object.
  2. The extracted data is used to populate the DB record with rich fields
     instead of raw text truncation.
  3. Falls back to keyword classification + raw-text storage if LLM is unavailable.

Target tables (PostgreSQL):
  incident    → incidents
  work_order  → managed_work_orders
  maintenance → maintenance_records
  note        → incidents (low-severity)

Knowledge base (Qdrant):
  ALL messages  → op_documents (type="slack_comms")
  incidents     → op_incidents
"""
from __future__ import annotations

import json
import re
import uuid
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)

_EQ_RE = re.compile(r"\b([A-Z]-\d{3}[A-Z]?|[A-Z]{1,3}-\d{2,4})\b")

_WO_KW = {
    "work order", "wo-", "ptw", "permit to work", "loto", "lock out",
    "isolation", "shutdown", "tag out", "scheduled maintenance",
    "planned maintenance", "pm order", "overdue pm",
}
_INC_KW = {
    "alarm", "alert", "failure", "breakdown", "leak", "vibration alarm",
    "overdue", "urgent", "emergency", "fault", "damaged", "trip",
    "high temperature", "high pressure", "spill", "fire", "injury",
    "near miss", "near-miss", "hazard", "unsafe", "above alarm",
    "exceeds", "exceeded alarm",
}
_MAINT_KW = {
    "maintenance", "lubrication", "pm ", "inspection", "service",
    "calibrat", "replace", "bearing", "overdue", "check",
    "measurement", "torque", "alignment", "vibration check",
    "maintenance order",
}
_SEV_MAP = {
    "p1": "P1", "p2": "P2", "p3": "P3", "p4": "P4",
    "critical": "P1", "high": "P2", "medium": "P3", "low": "P4",
    "urgent": "P2",
}


def _classify(text: str) -> str:
    tl = text.lower()
    if any(kw in tl for kw in _WO_KW):
        return "work_order"
    if any(kw in tl for kw in _INC_KW):
        return "incident"
    if any(kw in tl for kw in _MAINT_KW):
        return "maintenance"
    return "note"


def _severity(text: str) -> str:
    tl = text.lower()
    for kw, sev in _SEV_MAP.items():
        if kw in tl:
            return sev
    return "P4"


def _extract_equipment(text: str) -> list[str]:
    return list(dict.fromkeys(_EQ_RE.findall(text)))


def _make_id(prefix: str, slack_id: str) -> str:
    """Deterministic ID based on Slack message ID so we never duplicate."""
    clean = re.sub(r"[^A-Za-z0-9]", "", slack_id)[:12]
    return f"{prefix}-SLACK-{clean}"


async def _already_stored(record_id: str) -> bool:
    """Return True if a record with this ID already exists in any target table."""
    async with AsyncSessionLocal() as s:
        for model in (m.Incident, m.ManagedWorkOrder, m.MaintenanceRecord):
            row = (await s.execute(select(model).where(model.id == record_id))).scalar_one_or_none()
            if row:
                return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# LLM-powered extraction
# ─────────────────────────────────────────────────────────────────────────────

_LLM_SYSTEM = """You are an industrial plant operations assistant. Extract structured data
from the Slack message below and return ONLY valid JSON (no markdown, no extra text).

Return this schema:
{
  "classification": "incident|work_order|maintenance|note",
  "equipment_ids": ["P-101", ...],            // all equipment tags found (regex [A-Z]-DDD or XX-DDD)
  "severity": "P1|P2|P3|P4|P5",              // P1=critical P5=info
  "priority": "critical|high|medium|low",
  "title": "concise 1-sentence title (≤120 chars)",
  "description": "full technical summary (~2-3 sentences)",
  "root_cause_hint": "suspected root cause or null",
  "action_required": "immediate action text or null",
  "maintenance_type": "Preventive|Corrective|Predictive|Emergency",  // only for maintenance
  "wo_category": "corrective|preventive|predictive|emergency|shutdown|modification",
  "incident_type": "near_miss|first_aid|environmental|property_damage|fire|spill|other",
  "estimated_hours": null or number,
  "keywords": ["keyword1", "keyword2"]
}"""


async def _llm_extract(text: str, fallback_classification: str) -> dict[str, Any] | None:
    """Call LLM to extract structured fields from a Slack message.
    Returns parsed dict or None if LLM unavailable/fails."""
    try:
        from app.services.llm_service import _get_client
        from app.core.config import settings
        client = _get_client()
        if client is None:
            return None
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": f"SLACK MESSAGE:\n{text[:1500]}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=600,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        logger.debug("LLM extraction failed, using keyword fallback: %s", exc)
        return None


async def _store_incident(msg: dict[str, Any], extracted: dict[str, Any] | None = None) -> str | None:
    text   = msg.get("text", "")
    slack_id = msg.get("id", str(uuid.uuid4()))
    rec_id = _make_id("INC", slack_id)

    if await _already_stored(rec_id):
        return None

    eq_ids = (extracted or {}).get("equipment_ids") or _extract_equipment(text)
    eq_id  = eq_ids[0] if eq_ids else "UNKNOWN"
    sev    = (extracted or {}).get("severity") or _severity(text)
    title  = (extracted or {}).get("title") or text[:120]
    desc   = (extracted or {}).get("description") or text[:500]
    action = (extracted or {}).get("action_required")
    root   = (extracted or {}).get("root_cause_hint")
    kw     = (extracted or {}).get("keywords") or eq_ids

    dt = msg.get("timestamp", datetime.utcnow().isoformat())
    try:
        date_str = datetime.fromisoformat(dt).strftime("%Y-%m-%d")
    except Exception:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    record = m.Incident(
        id=rec_id,
        equipment_id=eq_id,
        date=date_str,
        title=title,
        severity=sev,
        symptom=desc,
        root_cause=root,
        action_taken=action,
        technician=msg.get("user_display"),
        keywords=kw,
        extra={
            "source": "slack",
            "channel": msg.get("channel"),
            "slack_message_id": slack_id,
            "ingested_at": datetime.utcnow().isoformat(),
            "ai_extracted": extracted is not None,
        },
    )
    async with AsyncSessionLocal() as s:
        stmt = pg_insert(m.Incident).values(
            id=record.id, equipment_id=record.equipment_id,
            date=record.date, title=record.title, severity=record.severity,
            symptom=record.symptom, root_cause=record.root_cause,
            action_taken=record.action_taken, technician=record.technician,
            keywords=record.keywords, extra=record.extra,
        ).on_conflict_do_nothing()
        await s.execute(stmt)
        await s.commit()
    logger.info("Slack→Incident stored: %s (%s) [ai=%s]", rec_id, eq_id, extracted is not None)
    return rec_id


async def _store_work_order(msg: dict[str, Any], extracted: dict[str, Any] | None = None) -> str | None:
    text     = msg.get("text", "")
    slack_id = msg.get("id", str(uuid.uuid4()))
    rec_id   = _make_id("MWO", slack_id)

    if await _already_stored(rec_id):
        return None

    eq_ids   = (extracted or {}).get("equipment_ids") or _extract_equipment(text)
    tl = text.lower()
    priority = (extracted or {}).get("priority") or (
        "critical" if any(k in tl for k in ("critical", "emergency")) else
        "high" if "urgent" in tl else "medium"
    )
    category = (extracted or {}).get("wo_category", "corrective")
    title    = (extracted or {}).get("title") or text[:120]
    desc     = (extracted or {}).get("description") or text[:500]
    est_hrs  = (extracted or {}).get("estimated_hours")

    wo_num = f"WO-SLACK-{rec_id[-8:]}"
    async with AsyncSessionLocal() as s:
        stmt = pg_insert(m.ManagedWorkOrder).values(
            id=rec_id,
            wo_number=wo_num,
            title=title,
            description=desc,
            category=category,
            priority=priority,
            status="submitted",
            equipment_ids=eq_ids or [],
            estimated_hours=est_hrs,
            created_by_name=msg.get("user_display"),
            audit_trail=[{
                "timestamp": datetime.utcnow().isoformat(),
                "action": "created",
                "user_name": "slack-ingestor",
                "comments": f"Auto-created from Slack message in {msg.get('channel')} [ai={extracted is not None}]",
            }],
        ).on_conflict_do_nothing()
        await s.execute(stmt)
        await s.commit()
    logger.info("Slack→ManagedWorkOrder stored: %s [ai=%s]", rec_id, extracted is not None)
    return rec_id


async def _store_maintenance(msg: dict[str, Any], extracted: dict[str, Any] | None = None) -> str | None:
    text     = msg.get("text", "")
    slack_id = msg.get("id", str(uuid.uuid4()))
    rec_id   = _make_id("MR", slack_id)

    if await _already_stored(rec_id):
        return None

    eq_ids  = (extracted or {}).get("equipment_ids") or _extract_equipment(text)
    eq_id   = eq_ids[0] if eq_ids else "UNKNOWN"
    mr_type = (extracted or {}).get("maintenance_type", "Corrective")
    desc    = (extracted or {}).get("description") or text[:500]
    action  = (extracted or {}).get("action_required")

    dt = msg.get("timestamp", datetime.utcnow().isoformat())
    try:
        date_str = datetime.fromisoformat(dt).strftime("%Y-%m-%d")
    except Exception:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    async with AsyncSessionLocal() as s:
        stmt = pg_insert(m.MaintenanceRecord).values(
            id=rec_id,
            equipment_id=eq_id,
            date=date_str,
            type=mr_type,
            description=desc,
            findings=action,
            status="Pending",
            technician=msg.get("user_display"),
            extra={
                "source": "slack",
                "channel": msg.get("channel"),
                "slack_message_id": slack_id,
                "ingested_at": datetime.utcnow().isoformat(),
                "ai_extracted": extracted is not None,
            },
        ).on_conflict_do_nothing()
        await s.execute(stmt)
        await s.commit()
    logger.info("Slack→MaintenanceRecord stored: %s (%s) [ai=%s]", rec_id, eq_id, extracted is not None)
    return rec_id


async def ingest_slack_messages(messages: list[dict[str, Any]]) -> dict[str, int]:
    """
    Classify and persist a list of Slack messages into the DB AND knowledge base.

    For each message:
      1. LLM extracts structured fields (classification, title, description,
         equipment IDs, severity, action required, etc.) — falls back to
         keyword matching if LLM is unavailable.
      2. The right form object is created with the rich extracted data.
      3. Message is indexed into Qdrant for vector search.

    Returns: {incidents, work_orders, maintenance, notes, skipped}
    """
    counts = {"incidents": 0, "work_orders": 0, "maintenance": 0, "notes": 0, "skipped": 0}

    for msg in messages:
        text = msg.get("text", "")
        if not text.strip():
            counts["skipped"] += 1
            continue

        # ── LLM extraction (primary) ─────────────────────────────────────────
        # Use keyword classification as initial hint, then let LLM refine
        kw_classification = _classify(text)
        extracted = await _llm_extract(text, kw_classification)

        classification = (extracted or {}).get("classification") or kw_classification
        eq_ids = (extracted or {}).get("equipment_ids") or _extract_equipment(text)

        # Skip messages with no equipment mention at all
        if not eq_ids and not msg.get("equipment_mentions"):
            counts["skipped"] += 1
            continue
        if not eq_ids and msg.get("equipment_mentions"):
            eq_ids = msg["equipment_mentions"]

        try:
            if classification == "work_order":
                result = await _store_work_order(msg, extracted)
                if result:
                    await _index_to_kb(result, msg, eq_ids, "work_order")
                    counts["work_orders"] += 1
                else:
                    counts["skipped"] += 1
            elif classification == "incident":
                result = await _store_incident(msg, extracted)
                if result:
                    await _index_to_kb(result, msg, eq_ids, "incident")
                    counts["incidents"] += 1
                else:
                    counts["skipped"] += 1
            elif classification == "maintenance":
                result = await _store_maintenance(msg, extracted)
                if result:
                    await _index_to_kb(result, msg, eq_ids, "maintenance")
                    counts["maintenance"] += 1
                else:
                    counts["skipped"] += 1
            else:
                # note — store as low-severity incident
                patched = dict(msg)
                if extracted:
                    extracted["severity"] = extracted.get("severity", "P4")
                result = await _store_incident(patched, extracted)
                if result:
                    await _index_to_kb(result, msg, eq_ids, "note")
                    counts["notes"] += 1
                else:
                    counts["skipped"] += 1
        except Exception as exc:
            logger.warning("Slack ingest error for msg %s: %s", msg.get("id"), exc)
            counts["skipped"] += 1

    return counts



# ─────────────────────────────────────────────────────────────────────────────
# Knowledge-base indexing
# ─────────────────────────────────────────────────────────────────────────────

async def _index_to_kb(record_id: str, msg: dict[str, Any],
                        eq_ids: list[str], classification: str) -> None:
    """
    Index a Slack message into the Qdrant knowledge base so the AI agent can
    retrieve it during semantic search alongside documents and incidents.

    Two collections are populated:
      op_documents — all messages as comms document sections
      op_incidents — incident/work_order messages for similarity search
    """
    try:
        from app.services import vector_service as vs
        text = msg.get("text", "")
        dt   = msg.get("timestamp", datetime.utcnow().isoformat())
        channel = msg.get("channel", "slack")
        user    = msg.get("user_display", "unknown")
        eq_id   = eq_ids[0] if eq_ids else "UNKNOWN"
        try:
            date_str = datetime.fromisoformat(dt).strftime("%Y-%m-%d")
        except Exception:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        # 1. Index as document section (op_documents) — visible to document intelligence agent
        doc_id   = f"SLACK-DOC-{record_id}"
        doc_name = f"Slack [{channel}] {user} — {date_str}"
        await vs.index_document_section(
            doc_id=doc_id,
            doc_name=doc_name,
            section_id="body",
            text=text[:600],
            equipment_ids=eq_ids,
            doc_type="slack_comms",
        )

        # 2. Save a DocumentRecord in PostgreSQL so it appears in the Documents list
        await _save_document_record(doc_id, doc_name, eq_ids, text, classification, channel, user, date_str)

        # 3. For incident/work_order messages, also index into op_incidents
        if classification in ("incident", "work_order", "note"):
            severity = _severity(text)
            await vs.index_incident(
                incident_id=record_id,
                title=text[:100],
                description=text[:500],
                equipment_id=eq_id,
                severity=severity,
                date=date_str,
            )
    except Exception as exc:
        logger.warning("KB indexing failed for %s: %s", record_id, exc)


async def _save_document_record(doc_id: str, doc_name: str, eq_ids: list[str],
                                  text: str, classification: str,
                                  channel: str, user: str, date_str: str) -> None:
    """Save a DocumentRecord to PostgreSQL so Slack messages appear in the Documents list."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert_doc
    async with AsyncSessionLocal() as s:
        stmt = pg_insert_doc(m.DocumentRecord).values(
            id=doc_id,
            name=doc_name,
            type="slack_comms",
            equipment_ids=eq_ids,
            date=date_str,
            status="processed",
            sections={"body": text[:2000]},
            entities={
                "equipment_ids": eq_ids,
                "document_type": "slack_comms",
                "summary": f"Slack message from {user} in {channel}",
                "classification": classification,
            },
            pipeline_steps={s: "done" for s in ["saved", "extracted", "entities", "graph", "indexed"]},
            current_step="done",
        ).on_conflict_do_nothing()
        await s.execute(stmt)
        await s.commit()
