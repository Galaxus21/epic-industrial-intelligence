"""
AI Operations Brain — Compliance API
Returns regulatory compliance status across all equipment.
Now includes write endpoints so compliance records can be updated at runtime
instead of being permanently frozen at seed values.

Endpoints
---------
  GET  /api/v1/compliance/analyze          AI plant-wide analysis
  GET  /api/v1/compliance                  all equipment scores
  GET  /api/v1/compliance/{id}             one equipment
  POST /api/v1/compliance/{id}             create or overwrite compliance record
  PATCH /api/v1/compliance/{id}            update specific fields (score, status)
  POST /api/v1/compliance/{id}/resolve-issue  mark a specific issue as resolved
"""
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import db_service as db
from app.services.audit import audit

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ComplianceIssue(BaseModel):
    id: str = ""
    item: str
    severity: str = "Medium"       # Low | Medium | High | Critical
    standard: str = ""             # e.g. OISD-117, API 610
    finding: str = ""
    due_date: str | None = None
    resolved: bool = False


class ComplianceUpsert(BaseModel):
    overall_score: int = 100
    status: str = "Compliant"      # Compliant | Warning | Non-Compliant | Critical
    issues: list[dict] = []
    passed: list[dict] = []


class CompliancePatch(BaseModel):
    overall_score: int | None = None
    status: str | None = None


class ResolveIssue(BaseModel):
    item: str                      # exact text of the issue item to resolve
    resolved_by: str = "user"
    resolution_note: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_to_status(score: int) -> str:
    if score >= 90: return "Compliant"
    if score >= 75: return "Warning"
    if score >= 50: return "Non-Compliant"
    return "Critical"


# ── Read endpoints ────────────────────────────────────────────────────────────

@router.get("/analyze")
async def get_compliance_ai_analysis():
    """Return AI-generated plant-wide compliance analysis with prioritised action items."""
    from app.services import llm_service

    all_compliance_raw = await db.get_all_compliance()
    all_equipment = await db.get_all_equipment_list()
    eq_map = {e["id"]: e for e in all_equipment}

    enriched = []
    for c in all_compliance_raw:
        eq = eq_map.get(c.get("equipment_id", ""), {})
        enriched.append({
            **c,
            "equipment_name": eq.get("name", c.get("equipment_id", "")),
            "high_issues": len([i for i in (c.get("issues") or []) if i.get("severity") == "High"]),
            "total_issues": len(c.get("issues") or []),
        })

    analysis = await llm_service.analyze_compliance_plant(enriched, all_equipment)
    return analysis


@router.get("")
async def get_compliance_overview():
    """Return compliance status for all equipment."""
    all_compliance = await db.get_all_compliance()
    overview = []
    for status in all_compliance:
        eq = await db.get_equipment(status["equipment_id"]) or {}
        overview.append({
            "equipment_id":   status["equipment_id"],
            "equipment_name": eq.get("name", status["equipment_id"]),
            "overall_score":  status.get("overall_score"),
            "status":         status.get("status"),
            "high_issues":    len([i for i in (status.get("issues") or []) if i.get("severity") == "High"]),
            "total_issues":   len(status.get("issues") or []),
            "passed_count":   len(status.get("passed") or []),
            "issues":         status.get("issues") or [],
        })
    return overview


@router.get("/{equipment_id}")
async def get_equipment_compliance(equipment_id: str):
    """Return detailed compliance status for one equipment."""
    compliance = await db.get_compliance(equipment_id)
    if compliance is None:
        eq = await db.get_equipment(equipment_id)
        if eq is None:
            raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
        return {"equipment_id": equipment_id, "overall_score": 100, "status": "Compliant", "issues": [], "passed": []}
    return compliance


# ── Write endpoints ───────────────────────────────────────────────────────────

@router.post("/{equipment_id}", status_code=201)
async def upsert_equipment_compliance(equipment_id: str, body: ComplianceUpsert):
    """Create or fully replace the compliance record for an equipment."""
    eq = await db.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(404, f"Equipment '{equipment_id}' not found")

    # Ensure all issues have an id
    issues = []
    for issue in body.issues:
        if not issue.get("id"):
            issue = {**issue, "id": uuid.uuid4().hex[:8].upper()}
        issues.append(issue)

    status = _score_to_status(body.overall_score)
    await db.upsert_compliance({
        "equipment_id":  equipment_id,
        "overall_score": body.overall_score,
        "status":        status,
        "issues":        issues,
        "passed":        body.passed,
    })
    audit("update", "compliance", equipment_id, equipment_id=equipment_id,
          actor="user", notes=f"Compliance record upserted. Score: {body.overall_score}%")
    return await db.get_compliance(equipment_id)


@router.patch("/{equipment_id}")
async def patch_compliance(equipment_id: str, body: CompliancePatch):
    """Update only score and/or status without touching issues."""
    existing = await db.get_compliance(equipment_id)
    if existing is None:
        raise HTTPException(404, f"No compliance record for '{equipment_id}'")

    updates: dict[str, Any] = {"equipment_id": equipment_id}
    if body.overall_score is not None:
        updates["overall_score"] = body.overall_score
        if body.status is None:
            updates["status"] = _score_to_status(body.overall_score)
    if body.status is not None:
        updates["status"] = body.status

    # Preserve existing issues/passed
    await db.upsert_compliance({**existing, **updates})
    audit("update", "compliance", equipment_id, equipment_id=equipment_id,
          actor="user", notes=f"Patched: {updates}")
    return await db.get_compliance(equipment_id)


@router.post("/{equipment_id}/resolve-issue")
async def resolve_compliance_issue(equipment_id: str, body: ResolveIssue):
    """
    Mark a specific compliance issue as resolved.
    Moves it from the `issues` list to `passed`, then recalculates the score.
    """
    existing = await db.get_compliance(equipment_id)
    if existing is None:
        raise HTTPException(404, f"No compliance record for '{equipment_id}'")

    issues: list[dict] = list(existing.get("issues") or [])
    passed: list[dict] = list(existing.get("passed") or [])

    # Find the matching issue (by item text or id)
    matched = None
    remaining = []
    for issue in issues:
        if issue.get("item") == body.item or issue.get("id") == body.item:
            matched = issue
        else:
            remaining.append(issue)

    if matched is None:
        raise HTTPException(404, f"Issue '{body.item}' not found in compliance record")

    resolved_issue = {
        **matched,
        "resolved": True,
        "resolved_by": body.resolved_by,
        "resolved_at": datetime.utcnow().isoformat(),
        "resolution_note": body.resolution_note,
    }
    passed.append(resolved_issue)

    # Recalculate score: base 100, subtract points per remaining severity
    sev_penalty = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
    new_score = max(0, 100 - sum(sev_penalty.get(i.get("severity", "Medium"), 5) for i in remaining))
    new_status = _score_to_status(new_score)

    await db.upsert_compliance({
        "equipment_id":  equipment_id,
        "overall_score": new_score,
        "status":        new_status,
        "issues":        remaining,
        "passed":        passed,
    })
    audit("update", "compliance", equipment_id, equipment_id=equipment_id,
          actor=body.resolved_by, notes=f"Issue resolved: {body.item}. New score: {new_score}%")
    return {
        "equipment_id":   equipment_id,
        "resolved_issue": matched.get("item"),
        "new_score":      new_score,
        "new_status":     new_status,
        "open_issues":    len(remaining),
    }

