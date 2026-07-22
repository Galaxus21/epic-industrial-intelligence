"""
AI Operations Brain — Email Message Ingestor
Classifies incoming emails and persists them into the DB AND knowledge base
following the same principle as the Slack ingestor and document pipeline:

  Every data ingestion → PostgreSQL relational tables + Qdrant knowledge base

Classification:
  incident    — alarm/alert/failure/vibration/urgent/overdue
  work_order  — WO/PTW/permit/shutdown/scheduled maintenance
  maintenance — maintenance/lubrication/PM/inspection/service
  note        — OEM correspondence, vendor notices, general comms

Targets:
  PostgreSQL  → incidents / managed_work_orders / maintenance_records
  Qdrant op_documents   → email body as comms document section
  Qdrant op_incidents   → incident-class emails for similarity search
  PostgreSQL documents  → DocumentRecord so emails appear in Documents list
"""
from __future__ import annotations

import re
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
    "isolation", "shutdown", "planned maintenance", "pm order", "overdue pm",
    "maintenance order", "scheduled maintenance",
}
_INC_KW = {
    "alarm", "alert", "failure", "breakdown", "leak", "vibration alarm",
    "overdue", "urgent", "emergency", "fault", "damaged", "trip",
    "high temperature", "high pressure", "spill", "fire", "injury",
    "near miss", "hazard", "unsafe", "above alarm", "exceeds alarm",
}
_MAINT_KW = {
    "maintenance", "lubrication", "pm ", "inspection", "service",
    "calibrat", "replace", "bearing", "overdue", "check",
    "torque", "alignment", "vibration check",
}
_SEV_MAP = {
    "p1": "P1", "p2": "P2", "p3": "P3", "p4": "P4",
    "critical": "P1", "high": "P2", "urgent": "P2", "medium": "P3", "low": "P4",
}


def _classify(subject: str, body: str) -> str:
    combined = (subject + " " + body).lower()
    if any(kw in combined for kw in _WO_KW):
        return "work_order"
    if any(kw in combined for kw in _INC_KW):
        return "incident"
    if any(kw in combined for kw in _MAINT_KW):
        return "maintenance"
    return "note"


def _severity(subject: str, body: str) -> str:
    combined = (subject + " " + body).lower()
    for kw, sev in _SEV_MAP.items():
        if kw in combined:
            return sev
    return "P4"


def _extract_equipment(text: str) -> list[str]:
    return list(dict.fromkeys(_EQ_RE.findall(text)))


def _make_id(prefix: str, email_id: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]", "", email_id)[:12]
    return f"{prefix}-EMAIL-{clean}"


async def _already_stored(record_id: str) -> bool:
    async with AsyncSessionLocal() as s:
        for model in (m.Incident, m.ManagedWorkOrder, m.MaintenanceRecord):
            row = (await s.execute(select(model).where(model.id == record_id))).scalar_one_or_none()
            if row:
                return True
    return False


# ── DB store helpers ──────────────────────────────────────────────────────────

async def _store_incident(email: dict) -> str | None:
    subject = email.get("subject", "")
    body    = email.get("body", "")
    text    = f"{subject}\n\n{body}"
    combined_eq = _extract_equipment(text) or email.get("equipment_mentions", [])
    eq_id   = combined_eq[0] if combined_eq else "UNKNOWN"
    email_id = email.get("id", email.get("uid", ""))
    rec_id  = _make_id("INC", email_id)

    if await _already_stored(rec_id):
        return None

    date_str = _parse_date(email.get("date", ""))
    async with AsyncSessionLocal() as s:
        stmt = pg_insert(m.Incident).values(
            id=rec_id, equipment_id=eq_id, date=date_str,
            title=subject[:120], severity=_severity(subject, body),
            symptom=text[:500], technician=email.get("from"),
            keywords=combined_eq,
            extra={
                "source": "email", "from": email.get("from"),
                "to": email.get("to"), "email_id": email_id,
                "ingested_at": datetime.utcnow().isoformat(),
            },
        ).on_conflict_do_nothing()
        await s.execute(stmt)
        await s.commit()
    logger.info("Email→Incident stored: %s", rec_id)
    return rec_id


async def _store_work_order(email: dict) -> str | None:
    subject = email.get("subject", "")
    body    = email.get("body", "")
    text    = f"{subject}\n\n{body}"
    eq_ids  = _extract_equipment(text) or email.get("equipment_mentions", [])
    email_id = email.get("id", email.get("uid", ""))
    rec_id  = _make_id("MWO", email_id)

    if await _already_stored(rec_id):
        return None

    tl = text.lower()
    priority = "high" if any(k in tl for k in ("urgent", "emergency", "critical")) else "medium"
    wo_num = f"WO-EMAIL-{rec_id[-8:]}"
    async with AsyncSessionLocal() as s:
        stmt = pg_insert(m.ManagedWorkOrder).values(
            id=rec_id, wo_number=wo_num, title=subject[:120],
            description=text[:500], category="corrective",
            priority=priority, status="submitted",
            equipment_ids=eq_ids or [],
            created_by_name=email.get("from"),
            audit_trail=[{
                "timestamp": datetime.utcnow().isoformat(),
                "action": "create", "user_name": "email-ingestor",
                "comments": f"Auto-created from email: {email.get('subject', '')[:60]}",
            }],
        ).on_conflict_do_nothing()
        await s.execute(stmt)
        await s.commit()
    logger.info("Email→ManagedWorkOrder stored: %s", rec_id)
    return rec_id


async def _store_maintenance(email: dict) -> str | None:
    subject = email.get("subject", "")
    body    = email.get("body", "")
    text    = f"{subject}\n\n{body}"
    eq_ids  = _extract_equipment(text) or email.get("equipment_mentions", [])
    eq_id   = eq_ids[0] if eq_ids else "UNKNOWN"
    email_id = email.get("id", email.get("uid", ""))
    rec_id  = _make_id("MR", email_id)

    if await _already_stored(rec_id):
        return None

    async with AsyncSessionLocal() as s:
        stmt = pg_insert(m.MaintenanceRecord).values(
            id=rec_id, equipment_id=eq_id,
            date=_parse_date(email.get("date", "")),
            type="Corrective", description=text[:500],
            status="Pending", technician=email.get("from"),
            extra={
                "source": "email", "from": email.get("from"),
                "email_id": email_id,
                "ingested_at": datetime.utcnow().isoformat(),
            },
        ).on_conflict_do_nothing()
        await s.execute(stmt)
        await s.commit()
    logger.info("Email→MaintenanceRecord stored: %s", rec_id)
    return rec_id


def _parse_date(raw: str) -> str:
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d")
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d")


# ── Knowledge-base indexing ────────────────────────────────────────────────────

async def _index_to_kb(record_id: str, email: dict,
                        eq_ids: list[str], classification: str) -> None:
    """Index email into Qdrant op_documents and (for incidents) op_incidents."""
    try:
        from app.services import vector_service as vs
        subject  = email.get("subject", "")
        body     = email.get("body", "")
        text     = f"Subject: {subject}\n\n{body}"
        date_str = _parse_date(email.get("date", ""))
        sender   = email.get("from", "unknown")
        eq_id    = eq_ids[0] if eq_ids else "UNKNOWN"

        doc_id   = f"EMAIL-DOC-{record_id}"
        doc_name = f"Email: {subject[:60]} — {sender}"

        # Index as document section (op_documents)
        await vs.index_document_section(
            doc_id=doc_id,
            doc_name=doc_name,
            section_id="body",
            text=text[:600],
            equipment_ids=eq_ids,
            doc_type="email_comms",
        )

        # Save DocumentRecord in PostgreSQL
        await _save_document_record(doc_id, doc_name, eq_ids, text,
                                     classification, sender, date_str)

        # For incidents/work orders: also index into op_incidents
        if classification in ("incident", "work_order", "note"):
            await vs.index_incident(
                incident_id=record_id,
                title=subject[:100],
                description=body[:500],
                equipment_id=eq_id,
                severity=_severity(subject, body),
                date=date_str,
            )
    except Exception as exc:
        logger.warning("KB indexing failed for email %s: %s", record_id, exc)


async def _save_document_record(doc_id: str, doc_name: str, eq_ids: list[str],
                                  text: str, classification: str,
                                  sender: str, date_str: str) -> None:
    async with AsyncSessionLocal() as s:
        stmt = pg_insert(m.DocumentRecord).values(
            id=doc_id, name=doc_name, type="email_comms",
            equipment_ids=eq_ids, date=date_str, status="processed",
            sections={"body": text[:2000]},
            entities={
                "equipment_ids": eq_ids,
                "document_type": "email_comms",
                "summary": f"Email from {sender}",
                "classification": classification,
            },
            pipeline_steps={s: "done" for s in ["saved", "extracted", "entities", "graph", "indexed"]},
            current_step="done",
        ).on_conflict_do_nothing()
        await s.execute(stmt)
        await s.commit()


# ── Public entry point ────────────────────────────────────────────────────────

async def ingest_emails(emails: list[dict[str, Any]]) -> dict[str, int]:
    """
    Classify and persist a list of email messages into DB + knowledge base.
    Returns {incidents, work_orders, maintenance, notes, skipped}.
    """
    counts = {"incidents": 0, "work_orders": 0, "maintenance": 0, "notes": 0, "skipped": 0}

    for email in emails:
        subject = email.get("subject", "")
        body    = email.get("body", "")
        text    = f"{subject} {body}"
        eq_ids  = _extract_equipment(text) or email.get("equipment_mentions", [])

        if not eq_ids:
            counts["skipped"] += 1
            continue

        classification = _classify(subject, body)
        try:
            if classification == "work_order":
                result = await _store_work_order(email)
                if result:
                    await _index_to_kb(result, email, eq_ids, "work_order")
                    counts["work_orders"] += 1
                else:
                    counts["skipped"] += 1
            elif classification == "incident":
                result = await _store_incident(email)
                if result:
                    await _index_to_kb(result, email, eq_ids, "incident")
                    counts["incidents"] += 1
                else:
                    counts["skipped"] += 1
            elif classification == "maintenance":
                result = await _store_maintenance(email)
                if result:
                    await _index_to_kb(result, email, eq_ids, "maintenance")
                    counts["maintenance"] += 1
                else:
                    counts["skipped"] += 1
            else:
                result = await _store_incident(email)
                if result:
                    await _index_to_kb(result, email, eq_ids, "note")
                    counts["notes"] += 1
                else:
                    counts["skipped"] += 1
        except Exception as exc:
            logger.warning("Email ingest error for %s: %s", email.get("id"), exc)
            counts["skipped"] += 1

    return counts
