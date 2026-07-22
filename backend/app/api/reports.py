"""
AI Operations Brain — Reports & Analytics API
Pre-computed KPIs and trend reports for the operations dashboard.

Endpoints:
  GET /api/v1/reports/overview      — plant-wide KPI snapshot
  GET /api/v1/reports/equipment     — per-equipment health matrix
  GET /api/v1/reports/maintenance   — maintenance KPIs (MTBF, compliance %)
  GET /api/v1/reports/incidents     — incident frequency, severity breakdown
  GET /api/v1/reports/work-orders   — WO analytics (open/closed, avg duration)
  GET /api/v1/reports/safety        — PTW conflicts, compliance scores
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, date, timedelta
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select, func

from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services import db_service as db

logger = logging.getLogger(__name__)
router = APIRouter()

_TODAY = date.today()
_30D_AGO = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
_90D_AGO = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")

# IncidentReport severity → display label
_P_TO_SEV: dict[str, str] = {
    "P1": "Critical", "P2": "Critical",
    "P3": "High",     "P4": "Medium",    "P5": "Low",
}

# ManagedWorkOrder statuses that count as "open"
_MWO_OPEN = {"draft", "submitted", "pending_approval", "approved", "scheduled", "in_progress", "pending_verification"}
# ManagedWorkOrder statuses that count as "completed / closed"
_MWO_DONE = {"verified", "closed"}


def _pct(a: int, b: int) -> float:
    return round(a / b * 100, 1) if b else 0.0


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("/overview")
async def get_overview():
    """Plant-wide KPI snapshot — aggregates ALL workflow tables."""
    all_eq = await db.get_all_equipment_list()
    active = [e for e in all_eq if not e.get("_discovered") and e.get("type")]

    # Equipment health
    health_scores = [e["health_score"] for e in active if e.get("health_score") is not None]
    avg_health = round(sum(health_scores) / len(health_scores), 1) if health_scores else None
    in_alarm = sum(
        1 for e in active
        if any(
            isinstance(r, dict) and r.get("value") is not None and r.get("alarm") is not None
            and r["value"] > r["alarm"]
            for r in (e.get("current_readings") or {}).values()
        )
    )
    overdue_maint = sum(1 for e in active if (e.get("maintenance_due_days") or 999) <= 0)
    compliance_low = sum(1 for e in active if (e.get("compliance_score") or 100) < 90)

    async with AsyncSessionLocal() as s:
        # Legacy work orders (AI-generated)
        wo_all  = (await s.execute(select(func.count()).select_from(m.SavedWorkOrder))).scalar_one()
        wo_open = (await s.execute(select(func.count()).select_from(m.SavedWorkOrder).where(
            m.SavedWorkOrder.status.in_(["open", "in_progress"])))).scalar_one()
        wo_done = (await s.execute(select(func.count()).select_from(m.SavedWorkOrder).where(
            m.SavedWorkOrder.status == "completed"))).scalar_one()
        # Managed work orders (workflow)
        mwo_all  = (await s.execute(select(func.count()).select_from(m.ManagedWorkOrder))).scalar_one()
        mwo_open = (await s.execute(select(func.count()).select_from(m.ManagedWorkOrder).where(
            m.ManagedWorkOrder.status.in_(list(_MWO_OPEN))))).scalar_one()
        mwo_done = (await s.execute(select(func.count()).select_from(m.ManagedWorkOrder).where(
            m.ManagedWorkOrder.status.in_(list(_MWO_DONE))))).scalar_one()
        # Legacy incidents
        inc_all  = (await s.execute(select(func.count()).select_from(m.Incident))).scalar_one()
        inc_high = (await s.execute(select(func.count()).select_from(m.Incident).where(
            m.Incident.severity.in_(["Critical", "High"])))).scalar_one()
        # Formal incident reports
        ir_all   = (await s.execute(select(func.count()).select_from(m.IncidentReport))).scalar_one()
        ir_high  = (await s.execute(select(func.count()).select_from(m.IncidentReport).where(
            m.IncidentReport.severity.in_(["P1", "P2", "P3"])))).scalar_one()   # P3 = High
        # Checklists
        cl_open = (await s.execute(select(func.count()).select_from(m.SavedChecklist).where(
            m.SavedChecklist.status != "completed"))).scalar_one()
        cl_done = (await s.execute(select(func.count()).select_from(m.SavedChecklist).where(
            m.SavedChecklist.status == "completed"))).scalar_one()
        # Active permits
        ptw_active = (await s.execute(select(func.count()).select_from(m.PermitToWork).where(
            m.PermitToWork.status.in_(["active", "issued", "submitted",
                                        "area_authority_review", "safety_review", "ap_approval"])))).scalar_one()
        # Open inspections
        qi_open = (await s.execute(select(func.count()).select_from(m.QualityInspection).where(
            m.QualityInspection.status.in_(["scheduled", "in_progress"])))).scalar_one()
        # Active safety procedures
        sp_active = (await s.execute(select(func.count()).select_from(m.SafetyProcedure).where(
            m.SafetyProcedure.status == "active"))).scalar_one()
        # Audit events (last 7 days)
        audit_7d = (await s.execute(
            select(func.count()).select_from(m.AuditLog)
            .where(m.AuditLog.timestamp >= datetime.utcnow() - timedelta(days=7))
        )).scalar_one()

    total_wo   = wo_all + mwo_all
    total_open = wo_open + mwo_open
    total_done = wo_done + mwo_done
    total_inc  = inc_all + ir_all
    total_high = inc_high + ir_high

    return {
        "plant_health":        avg_health,
        "equipment_count":     len(active),
        "equipment_in_alarm":  in_alarm,
        "overdue_maintenance": overdue_maint,
        "compliance_issues":   compliance_low,
        "work_orders":  {"total": total_wo, "open": total_open, "completed": total_done,
                         "completion_rate": _pct(total_done, total_wo)},
        "incidents":    {"total": total_inc, "high_critical": total_high},
        "checklists":   {"open": cl_open, "completed": cl_done,
                         "completion_rate": _pct(cl_done, cl_open + cl_done)},
        "active_permits":     ptw_active,
        "open_inspections":   qi_open,
        "active_procedures":  sp_active,
        "audit_events_7d":    audit_7d,
        "generated_at":       datetime.utcnow().isoformat() + "Z",
    }


# ── Equipment health matrix ───────────────────────────────────────────────────

@router.get("/equipment")
async def get_equipment_report():
    """Per-equipment health, status, and open issue counts across all WO tables."""
    all_eq = await db.get_all_equipment_list()
    active = [e for e in all_eq if not e.get("_discovered") and e.get("type")]

    async with AsyncSessionLocal() as s:
        # Open legacy WOs per equipment
        wo_result = await s.execute(
            select(m.SavedWorkOrder.equipment_id, func.count())
            .where(m.SavedWorkOrder.status.in_(["open", "in_progress"]))
            .group_by(m.SavedWorkOrder.equipment_id)
        )
        open_wos: dict[str, int] = dict(wo_result.all())

        # Open managed WOs (equipment_ids is a JSON array — load and fan out in Python)
        mwo_result = await s.execute(
            select(m.ManagedWorkOrder.equipment_ids)
            .where(m.ManagedWorkOrder.status.in_(list(_MWO_OPEN)))
        )
        for (eq_ids,) in mwo_result.all():
            for eid in (eq_ids or []):
                open_wos[eid] = open_wos.get(eid, 0) + 1

        # Open incident reports per equipment
        ir_result = await s.execute(
            select(m.IncidentReport.equipment_ids)
            .where(m.IncidentReport.status.notin_(["closed"]))
        )
        open_incidents: dict[str, int] = {}
        for (eq_ids,) in ir_result.all():
            for eid in (eq_ids or []):
                open_incidents[eid] = open_incidents.get(eid, 0) + 1

    rows = []
    for eq in active:
        readings = eq.get("current_readings") or {}
        alarm_sensors = [k for k, r in readings.items()
                         if isinstance(r, dict) and r.get("alarm") and r.get("value", 0) > r["alarm"]]
        rows.append({
            "id":                  eq["id"],
            "name":                eq.get("name"),
            "type":                eq.get("type"),
            "location":            eq.get("location"),
            "health_score":        eq.get("health_score"),
            "failure_probability": eq.get("failure_probability"),
            "compliance_score":    eq.get("compliance_score"),
            "maintenance_due_days":eq.get("maintenance_due_days"),
            "status":              eq.get("status"),
            "criticality":         eq.get("criticality"),
            "alarm_sensors":       alarm_sensors,
            "open_work_orders":    open_wos.get(eq["id"], 0),
            "open_incidents":      open_incidents.get(eq["id"], 0),
        })

    rows.sort(key=lambda x: (x["health_score"] or 100))   # worst first
    return {"equipment": rows, "count": len(rows)}


# ── Maintenance KPIs ──────────────────────────────────────────────────────────

@router.get("/maintenance")
async def get_maintenance_report():
    """Maintenance compliance, MTBF proxy, and breakdown by type."""
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(m.MaintenanceRecord))
        all_mr = result.scalars().all()

    total      = len(all_mr)
    completed  = sum(1 for r in all_mr if r.status == "Completed")
    overdue    = sum(1 for r in all_mr if r.status == "Overdue")
    scheduled  = sum(1 for r in all_mr if r.status == "Scheduled")

    # By type
    by_type: dict[str, int] = defaultdict(int)
    for r in all_mr:
        by_type[r.type or "Unknown"] += 1

    # By equipment
    by_equipment: dict[str, dict] = defaultdict(lambda: {"total": 0, "completed": 0, "overdue": 0})
    for r in all_mr:
        eid = r.equipment_id
        by_equipment[eid]["total"] += 1
        if r.status == "Completed":  by_equipment[eid]["completed"] += 1
        if r.status == "Overdue":    by_equipment[eid]["overdue"]   += 1

    # Recent (last 30 days)
    recent_ids = {
        r.equipment_id for r in all_mr
        if r.status == "Completed" and (r.date or "") >= _30D_AGO
    }

    return {
        "kpis": {
            "total_records":       total,
            "completed":           completed,
            "overdue":             overdue,
            "scheduled":           scheduled,
            "compliance_rate_pct": _pct(completed, total),
        },
        "by_type":      dict(by_type),
        "by_equipment": [
            {"equipment_id": eid, **v} for eid, v in sorted(
                by_equipment.items(), key=lambda x: -x[1]["overdue"]
            )
        ],
        "recent_activity": {
            "equipment_serviced_30d": len(recent_ids),
            "records_last_30d": sum(1 for r in all_mr if (r.date or "") >= _30D_AGO),
        },
    }


# ── Incident analysis ─────────────────────────────────────────────────────────

@router.get("/incidents")
async def get_incident_report():
    """Incident frequency from BOTH legacy Incident and formal IncidentReport tables."""
    async with AsyncSessionLocal() as s:
        legacy_rows = (await s.execute(select(m.Incident))).scalars().all()
        ir_rows     = (await s.execute(
            select(m.IncidentReport).order_by(m.IncidentReport.created_at.desc())
        )).scalars().all()

    # ── Legacy incidents ──────────────────────────────────────────────────────
    real      = [r for r in legacy_rows if not r.id.startswith("LESSON-") and not r.id.startswith("PTW-")]
    lessons   = [r for r in legacy_rows if r.id.startswith("LESSON-")]
    ptw_checks= [r for r in legacy_rows if r.id.startswith("PTW-")]

    by_severity: dict[str, int] = defaultdict(int)
    by_equipment: dict[str, int] = defaultdict(int)
    by_rcc: dict[str, int] = defaultdict(int)
    monthly: dict[str, int] = defaultdict(int)
    downtimes: list[float] = []
    costs: list[float] = []

    for r in real:
        sev = r.severity or "Unknown"
        by_severity[sev] += 1
        by_equipment[r.equipment_id] += 1
        # root_cause_category: legacy incidents only — NOT used for cost/downtime
        # (those fields are demo seed values; we exclude them from cost/downtime aggregates)
        by_rcc[r.root_cause_category or "Unknown"] += 1
        if r.date:          monthly[r.date[:7]] += 1
        # ⚠️  Do NOT add cost_usd / downtime_hours from legacy incidents —
        # those values are hardcoded demo data.

    # ── Formal IncidentReport rows ────────────────────────────────────────────
    for r in ir_rows:
        sev = _P_TO_SEV.get(r.severity or "", r.severity or "Unknown")
        by_severity[sev] += 1
        eq_id = (r.equipment_ids or ["UNKNOWN"])[0]
        by_equipment[eq_id] += 1
        date_str = (r.occurred_at or r.reported_at or "")[:7]
        if date_str:
            monthly[date_str] += 1
        # Cost and downtime come from live IncidentReport rows ONLY
        if r.downtime_hours:
            downtimes.append(r.downtime_hours)
        if r.cost_usd:
            costs.append(r.cost_usd)
        # Root cause category from live investigation or incident_type as fallback
        rcc = r.root_cause_category or r.incident_type or "Unknown"
        by_rcc[rcc] += 1

    high_critical = by_severity.get("Critical", 0) + by_severity.get("High", 0)
    avg_downtime = round(sum(downtimes) / len(downtimes), 1) if downtimes else 0

    # ── recent_incidents: ONLY IncidentReport rows (user-submitted, live data)
    # Legacy seeded incidents (INC-2022-034 etc.) are intentionally excluded here
    # so the list is always real operational data, not demo seed records.
    recent: list[dict[str, Any]] = [
        {
            "id":              r.id,
            "incident_number": r.incident_number,
            "equipment_id":    (r.equipment_ids or [""])[0],
            "title":           r.title,
            "severity":        _P_TO_SEV.get(r.severity or "", r.severity or "Unknown"),
            "date":            (r.occurred_at or r.reported_at or "")[:10],
            "status":          r.status,
            "incident_type":   r.incident_type,
        }
        for r in ir_rows[:15]
    ]

    return {
        "summary": {
            "total":                 len(real) + len(ir_rows),
            "legacy_count":          len(real),
            "reported_count":        len(ir_rows),
            "high_critical":         high_critical,
            "avg_downtime_hours":    avg_downtime,
            "total_cost_usd":        sum(costs),
            "lessons_learned_count": len(lessons),
            "ptw_conflict_checks":   len(ptw_checks),
        },
        "by_severity":  dict(by_severity),
        "by_equipment": [
            {"equipment_id": eid, "count": cnt}
            for eid, cnt in sorted(by_equipment.items(), key=lambda x: -x[1])
        ],
        "by_root_cause": dict(by_rcc),
        "monthly_trend": [
            {"month": mo, "count": c}
            for mo, c in sorted(monthly.items())
        ],
        "recent_incidents": recent[:10],
    }


# ── Work order analytics ──────────────────────────────────────────────────────

@router.get("/work-orders")
async def get_work_order_report():
    """WO analytics across SavedWorkOrder (AI/legacy) and ManagedWorkOrder (workflow)."""
    async with AsyncSessionLocal() as s:
        saved_rows = (await s.execute(
            select(m.SavedWorkOrder).order_by(m.SavedWorkOrder.created_at.desc())
        )).scalars().all()
        mwo_rows = (await s.execute(
            select(m.ManagedWorkOrder).order_by(m.ManagedWorkOrder.created_at.desc())
        )).scalars().all()

    by_status: dict[str, int] = defaultdict(int)
    by_type:   dict[str, int] = defaultdict(int)
    by_eq:     dict[str, int] = defaultdict(int)
    durations: list[float] = []

    # ── Legacy SavedWorkOrder ─────────────────────────────────────────────────
    for wo in saved_rows:
        by_status[wo.status or "unknown"] += 1
        by_type[wo.wo_type or "Unknown"] += 1
        by_eq[wo.equipment_id] += 1
        if wo.actual_duration_hours:
            durations.append(wo.actual_duration_hours)

    solved     = sum(1 for w in saved_rows if w.solution_worked is True)
    not_solved = sum(1 for w in saved_rows if w.solution_worked is False)

    # ── ManagedWorkOrder ──────────────────────────────────────────────────────
    # Map granular statuses to simplified buckets
    _status_map = {
        "draft": "open", "submitted": "open", "pending_approval": "open",
        "approved": "open", "scheduled": "open", "in_progress": "in_progress",
        "pending_verification": "in_progress",
        "verified": "completed", "closed": "completed", "cancelled": "cancelled",
    }
    for wo in mwo_rows:
        bucket = _status_map.get(wo.status or "", wo.status or "unknown")
        by_status[bucket] += 1
        by_type[wo.category or "Unknown"] += 1
        for eid in (wo.equipment_ids or []):
            by_eq[eid] += 1
        if wo.actual_hours:
            durations.append(wo.actual_hours)

    total_all  = len(saved_rows) + len(mwo_rows)
    total_open = by_status.get("open", 0) + by_status.get("in_progress", 0)
    total_done = by_status.get("completed", 0)
    cutoff_30d = datetime.utcnow() - timedelta(days=30)
    created_30d = (
        sum(1 for w in saved_rows if w.created_at and w.created_at >= cutoff_30d)
        + sum(1 for w in mwo_rows  if w.created_at and w.created_at >= cutoff_30d)
    )

    # ── Recent list (mix of both, sorted by created_at desc) ─────────────────
    recent_saved = [
        {
            "id": w.id, "equipment_id": w.equipment_id,
            "type": w.wo_type, "category": "legacy",
            "status": w.status, "risk_level": w.risk_level or "",
            "description": (w.description or "")[:80],
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in saved_rows[:10]
    ]
    recent_mwo = [
        {
            "id": w.id, "equipment_id": (w.equipment_ids or [""])[0],
            "type": w.wo_number, "category": w.category or "",
            "status": w.status, "risk_level": w.priority or "",
            "description": (w.title or "")[:80],
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in mwo_rows[:10]
    ]
    all_recent = sorted(
        recent_saved + recent_mwo,
        key=lambda x: x["created_at"] or "",
        reverse=True,
    )[:15]

    return {
        "summary": {
            "total":            total_all,
            "open":             total_open,
            "completed":        total_done,
            "solution_rate":    _pct(solved, solved + not_solved),
            "avg_duration_h":   round(sum(durations) / len(durations), 1) if durations else 0,
            "created_last_30d": created_30d,
            "managed_count":    len(mwo_rows),
            "legacy_count":     len(saved_rows),
        },
        "by_status": dict(by_status),
        "by_type":   dict(by_type),
        "by_equipment": [
            {"equipment_id": eid, "count": cnt}
            for eid, cnt in sorted(by_eq.items(), key=lambda x: -x[1])[:10]
        ],
        "recent": all_recent,
    }


# ── Safety & compliance ───────────────────────────────────────────────────────

@router.get("/safety")
async def get_safety_report():
    """Safety report from PermitToWork, SafetyProcedure, and compliance scores."""
    all_eq = await db.get_all_equipment_list()
    active = [e for e in all_eq if not e.get("_discovered") and e.get("type")]

    async with AsyncSessionLocal() as s:
        # Actual PermitToWork records (new workflow table)
        ptw_rows = (await s.execute(
            select(m.PermitToWork).order_by(m.PermitToWork.created_at.desc())
        )).scalars().all()

        # Safety procedures summary
        sp_by_status: dict[str, int] = defaultdict(int)
        for sp in (await s.execute(select(m.SafetyProcedure))).scalars().all():
            sp_by_status[sp.status or "unknown"] += 1

        # Legacy PTW-conflict incidents (fall back if new table is empty)
        legacy_ptw = (await s.execute(
            select(m.Incident).where(m.Incident.id.like("PTW-%"))
            .order_by(m.Incident.date.desc())
        )).scalars().all()

    # ── Compliance stats ──────────────────────────────────────────────────────
    scores = [e.get("compliance_score") for e in active if e.get("compliance_score") is not None]
    avg_compliance = round(sum(scores) / len(scores), 1) if scores else None
    below_90 = sum(1 for sc in scores if sc < 90)
    below_75 = sum(1 for sc in scores if sc < 75)

    # ── PTW analysis (prefer new table, fall back to legacy) ─────────────────
    ptw_by_clearance: dict[str, int] = defaultdict(int)
    ptw_by_eq: dict[str, int] = defaultdict(int)
    recent_ptw: list[dict[str, Any]] = []

    if ptw_rows:
        # Map PTW status → clearance bucket
        _ptw_blocked     = {"cancelled"}
        _ptw_conditional = {"draft", "submitted", "area_authority_review",
                            "safety_review", "ap_approval", "suspended"}
        for p in ptw_rows:
            if p.status in _ptw_blocked:
                ptw_by_clearance["BLOCKED"] += 1
            elif p.status in _ptw_conditional:
                ptw_by_clearance["CONDITIONAL"] += 1
            else:  # issued, active, closed, completion_requested
                ptw_by_clearance["CLEAR"] += 1
            for eid in (p.equipment_ids or []):
                ptw_by_eq[eid] = ptw_by_eq.get(eid, 0) + 1
        recent_ptw = [
            {
                "id":           p.id,
                "permit_number": p.permit_number,
                "equipment_id": (p.equipment_ids or [""])[0],
                "permit_type":  p.permit_type,
                "status":       p.status,
                "date":         (p.created_at.isoformat() if p.created_at else "")[:10],
                "title":        p.title,
                "action":       f"{p.permit_type} — {p.status}",
            }
            for p in ptw_rows[:10]
        ]
    else:
        # Fall back to legacy PTW-prefixed incidents
        for p in legacy_ptw:
            action = p.action_taken or ""
            if "BLOCKED" in action:       ptw_by_clearance["BLOCKED"] += 1
            elif "CONDITIONAL" in action: ptw_by_clearance["CONDITIONAL"] += 1
            else:                         ptw_by_clearance["CLEAR"] += 1
            ptw_by_eq[p.equipment_id] = ptw_by_eq.get(p.equipment_id, 0) + 1
        recent_ptw = [
            {"id": p.id, "equipment_id": p.equipment_id, "date": p.date or "",
             "title": p.title, "action": (p.action_taken or "")[:120]}
            for p in legacy_ptw[:10]
        ]

    total_ptw = len(ptw_rows) if ptw_rows else len(legacy_ptw)

    compliance_rows = [
        {"id": e["id"], "name": e.get("name"), "type": e.get("type"),
         "compliance_score": e.get("compliance_score"),
         "status": "Critical" if (e.get("compliance_score") or 100) < 75
                   else "Warning" if (e.get("compliance_score") or 100) < 90 else "OK"}
        for e in active if e.get("compliance_score") is not None
    ]
    compliance_rows.sort(key=lambda x: (x["compliance_score"] or 100))

    return {
        "summary": {
            "avg_compliance_pct":      avg_compliance,
            "equipment_below_90_pct":  below_90,
            "equipment_below_75_pct":  below_75,
            "total_ptw_checks":        total_ptw,
            "ptw_active":              ptw_by_clearance.get("CLEAR", 0),
            "ptw_blocked":             ptw_by_clearance.get("BLOCKED", 0),
            "ptw_conditional":         ptw_by_clearance.get("CONDITIONAL", 0),
            "active_procedures":       sp_by_status.get("active", 0),
            "procedures_in_review":    sp_by_status.get("peer_review", 0) + sp_by_status.get("technical_review", 0) + sp_by_status.get("final_approval", 0),
        },
        "compliance_by_equipment": compliance_rows[:20],
        "ptw_by_clearance":        dict(ptw_by_clearance),
        "ptw_by_equipment": [
            {"equipment_id": eid, "count": cnt}
            for eid, cnt in sorted(ptw_by_eq.items(), key=lambda x: -x[1])[:10]
        ],
        "recent_ptw_checks": recent_ptw,
        "procedures_by_status": dict(sp_by_status),
    }
