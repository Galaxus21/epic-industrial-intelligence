"""
AI Operations Brain — Root Cause Analysis (RCA) Engine
Investigates a production event and returns a ranked causal chain with probability scores.

Approach:
  1. Collect evidence from all sources: sensor anomalies, maintenance overdue,
     incidents, compliance gaps, equipment relationships.
  2. Call GPT-4.1 to synthesize a ranked probable-cause chain.
  3. Fall back to a heuristic engine when LLM is unavailable.

Endpoints:
  POST /api/v1/rca/analyze   — Run RCA on a symptom/event description
  GET  /api/v1/rca/events    — List of pre-defined production events for quick start
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.services import db_service as db
from app.services.anomalyService import detect_stored_anomalies
from app.services.alarmEvaluation import is_in_alarm, is_in_trip, alarm_direction
from app.services.llm_service import _get_client
from app.db import models as m

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Request / Response schemas ────────────────────────────────────────────────

class RCARequest(BaseModel):
    symptom: str
    equipment_id: str | None = None
    severity: str = "High"


class CausalStep(BaseModel):
    step: int
    event: str
    type: str          # root_cause | propagation | symptom
    equipment_id: str | None = None


class ProbableCause(BaseModel):
    rank: int
    cause: str
    probability: int
    evidence: list[str]
    equipment_affected: list[str]
    recommended_action: str
    timeframe: str


class RCAResponse(BaseModel):
    event: str
    equipment_id: str | None
    analysis_timestamp: str
    probable_causes: list[ProbableCause]
    causal_chain: list[CausalStep]
    sensor_anomalies: list[dict[str, Any]]
    ml_sensor_anomalies: list[dict[str, Any]] = []
    contributing_factors: list[str]
    recommended_next_steps: list[str]
    confidence: str        # High | Medium | Low
    analysis_source: str = "llm"  # "llm" | "heuristic"


# ── Evidence collector ────────────────────────────────────────────────────────

async def _collect_evidence(equipment_id: str | None) -> dict[str, Any]:
    """Gather all available evidence from DB for the RCA context."""
    evidence: dict[str, Any] = {
        "sensor_anomalies": [],
        "ml_sensor_anomalies": [],
        "overdue_maintenance": [],
        "recent_incidents": [],
    }

    # Sensor anomalies
    all_eq = await db.get_all_equipment_list()
    target_eq = (
        [next((e for e in all_eq if e["id"] == equipment_id), None)]
        if equipment_id else all_eq
    )
    target_eq = [e for e in target_eq if e]

    anomalies = []
    for eq in target_eq:
        readings: dict = eq.get("current_readings") or {}
        for sensor_name, reading in readings.items():
            if not isinstance(reading, dict):
                continue
            val = reading.get("value")
            alarm = reading.get("alarm")
            if is_in_alarm(val, reading):
                direction = alarm_direction(reading)
                excess_pct = round(abs(val - alarm) / alarm * 100, 1) if alarm else 0.0
                anomalies.append({
                    "equipment_id": eq["id"],
                    "equipment_name": eq.get("name", ""),
                    "sensor": sensor_name,
                    "value": val,
                    "unit": reading.get("unit", ""),
                    "alarm": alarm,
                    "excess_pct": excess_pct,
                    "alarm_direction": direction,
                })
    evidence["sensor_anomalies"] = anomalies

    # ML sensor anomalies from stored history
    ml_anomalies: list[dict[str, Any]] = []
    for eq in target_eq:
        try:
            ml_res = await detect_stored_anomalies(eq["id"])
            for sensor_name, s_data in ml_res.get("sensors", {}).items():
                for anom in s_data.get("anomalies", []):
                    ml_anomalies.append({
                        "equipment_id": eq["id"],
                        "equipment_name": eq.get("name", ""),
                        "sensor": sensor_name,
                        "ts": anom.get("ts"),
                        "value": anom.get("value"),
                        "score": anom.get("score"),
                    })
        except Exception as e:
            logger.warning("ML anomaly detection failed for %s: %s", eq["id"], e)
    evidence["ml_sensor_anomalies"] = ml_anomalies

    # Overdue maintenance
    all_maint: list[dict] = []
    ids_to_check = [e["id"] for e in target_eq] if target_eq else [equipment_id] if equipment_id else []
    for eid in ids_to_check:
        recs = await db.get_maintenance_records(eid)
        all_maint.extend([r for r in recs if r.get("status") == "Overdue"])
    evidence["overdue_maintenance"] = all_maint

    # Recent incidents
    for eid in ids_to_check:
        incs = await db.find_similar_incidents([])
        evidence["recent_incidents"].extend(incs[:3])

    # Equipment detail
    if equipment_id:
        eq_detail = await db.get_equipment(equipment_id)
        if eq_detail:
            evidence["equipment"] = {
                "id": eq_detail["id"],
                "name": eq_detail.get("name"),
                "type": eq_detail.get("type"),
                "health_score": eq_detail.get("health_score"),
                "failure_probability": eq_detail.get("failure_probability"),
                "compliance_score": eq_detail.get("compliance_score"),
                "maintenance_due_days": eq_detail.get("maintenance_due_days"),
            }

    return evidence


# ── LLM-based RCA ─────────────────────────────────────────────────────────────

_RCA_SYSTEM = """You are an expert industrial root cause analysis engineer with 30 years experience
in oil refineries and process plants. Given a reported symptom and evidence from sensors,
maintenance records, and incident history, perform a rigorous root cause analysis.

Return ONLY valid JSON — no markdown — matching this exact schema:
{
  "probable_causes": [
    {
      "rank": 1,
      "cause": "brief cause description",
      "probability": 82,
      "evidence": ["evidence item 1 with specific numbers", "evidence item 2"],
      "equipment_affected": ["EQUIP-ID"],
      "recommended_action": "specific action to take",
      "timeframe": "immediately|within 1h|within 4h|within 24h|planned"
    }
  ],
  "causal_chain": [
    {"step": 1, "event": "root trigger", "type": "root_cause", "equipment_id": "X"},
    {"step": 2, "event": "propagation step", "type": "propagation", "equipment_id": "X"},
    {"step": 3, "event": "observed symptom", "type": "symptom", "equipment_id": null}
  ],
  "contributing_factors": ["factor 1", "factor 2"],
  "recommended_next_steps": ["step 1", "step 2", "step 3"],
  "confidence": "High|Medium|Low"
}

Rules:
- Rank causes by probability (highest first), max 4 causes.
- Causal chain must have 3-6 steps flowing from root → propagation → symptom.
- Base probabilities on the actual sensor readings and evidence provided.
- Be specific — cite actual values (e.g. "vibration 7.2 mm/s exceeds 7.1 alarm").
- contributing_factors: list systemic issues (overdue maintenance, compliance gaps).
"""


async def _llm_rca(symptom: str, equipment_id: str | None, evidence: dict) -> dict | None:
    client = _get_client()
    if not client:
        return None
    try:
        user_msg = f"""Symptom: {symptom}
Equipment: {equipment_id or 'Multiple / Unknown'}

Evidence:
{json.dumps(evidence, indent=2, default=str)}

Perform root cause analysis and return JSON."""
        resp = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _RCA_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content or ""
        # strip potential markdown fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        logger.warning("RCA LLM call failed: %s", exc)
        return None


# ── Heuristic fallback ────────────────────────────────────────────────────────

def _heuristic_rca(symptom: str, equipment_id: str | None, evidence: dict) -> dict:
    """Rule-based RCA when LLM is unavailable."""
    anomalies = evidence.get("sensor_anomalies", [])
    overdue = evidence.get("overdue_maintenance", [])
    eq = evidence.get("equipment", {})
    symptom_l = symptom.lower()

    probable_causes = []

    # Vibration-related heuristics
    vib_anomaly = next((a for a in anomalies if "vibration" in a["sensor"].lower()), None)
    if vib_anomaly or "vibration" in symptom_l:
        probable_causes.append({
            "rank": 1,
            "cause": "Bearing lubrication degradation leading to increased friction and vibration",
            "probability": 75 if overdue else 55,
            "evidence": [
                f"Vibration on {vib_anomaly['equipment_id']} at {vib_anomaly['value']} {vib_anomaly['unit']} — alarm at {vib_anomaly['alarm']} ({vib_anomaly['excess_pct']}% over alarm)"
                if vib_anomaly else "Vibration reported above normal range",
                f"Lubrication maintenance overdue by {overdue[0].get('overdue_days', 'N/A')} days"
                if overdue else "Maintenance history indicates extended interval since last lubrication",
            ],
            "equipment_affected": [vib_anomaly["equipment_id"]] if vib_anomaly else ([equipment_id] if equipment_id else []),
            "recommended_action": "Immediately check lubrication level and quality. Apply fresh grease. If vibration persists, inspect bearing.",
            "timeframe": "within 1h",
        })
        probable_causes.append({
            "rank": 2,
            "cause": "Shaft misalignment due to thermal expansion or recent maintenance disturbance",
            "probability": 30,
            "evidence": ["Vibration characteristic consistent with misalignment (1× RPM component)"],
            "equipment_affected": [equipment_id] if equipment_id else [],
            "recommended_action": "Perform laser alignment check after next planned shutdown.",
            "timeframe": "within 24h",
        })

    # Flow/pressure drop heuristics
    if "production" in symptom_l or "flow" in symptom_l or "pressure" in symptom_l:
        probable_causes.append({
            "rank": len(probable_causes) + 1,
            "cause": "Partial valve restriction or blockage in feed line",
            "probability": 65,
            "evidence": [
                "Flow/pressure deviation reported without process condition change",
                "Feed valve positioner calibration may be drifting",
            ],
            "equipment_affected": [equipment_id] if equipment_id else [],
            "recommended_action": "Check all control valves in the affected line for position vs setpoint discrepancy.",
            "timeframe": "within 4h",
        })

    # Compliance gap contributing factor
    compliance_score = eq.get("compliance_score")
    if compliance_score and compliance_score < 90:
        probable_causes.append({
            "rank": len(probable_causes) + 1,
            "cause": f"Regulatory compliance gaps contributing to degraded equipment state (score: {compliance_score}%)",
            "probability": 20,
            "evidence": [f"Equipment compliance score at {compliance_score}% — below 90% threshold"],
            "equipment_affected": [equipment_id] if equipment_id else [],
            "recommended_action": "Review open compliance findings and close critical items.",
            "timeframe": "within 24h",
        })

    # Default if no heuristics matched
    if not probable_causes:
        probable_causes.append({
            "rank": 1,
            "cause": "Operational condition deviation — root cause requires further investigation",
            "probability": 50,
            "evidence": [f"Symptom: {symptom}"],
            "equipment_affected": [equipment_id] if equipment_id else [],
            "recommended_action": "Conduct physical inspection of the reported equipment.",
            "timeframe": "within 4h",
        })

    # Build causal chain
    eq_id = equipment_id or (anomalies[0]["equipment_id"] if anomalies else "Unknown")
    causal_chain = [
        {"step": 1, "event": probable_causes[0]["cause"], "type": "root_cause", "equipment_id": eq_id},
        {"step": 2, "event": "Equipment performance degradation", "type": "propagation", "equipment_id": eq_id},
        {"step": 3, "event": symptom, "type": "symptom", "equipment_id": None},
    ]

    contributing_factors: list[str] = []
    if overdue:
        contributing_factors.append(f"Overdue maintenance: {overdue[0].get('description', 'N/A')}")
    if compliance_score and compliance_score < 90:
        contributing_factors.append(f"Compliance score below threshold ({compliance_score}%)")
    if not contributing_factors:
        contributing_factors.append("No additional systemic contributing factors identified")

    # Normalize probabilities to sum to 100
    if probable_causes:
        raw_total = sum(c["probability"] for c in probable_causes)
        if raw_total > 0:
            for c in probable_causes:
                c["probability"] = round(c["probability"] * 100 / raw_total)
            diff = 100 - sum(c["probability"] for c in probable_causes)
            probable_causes[0]["probability"] += diff

    # Dynamic confidence based on evidence signals
    evidence_signals = len(anomalies) + len(overdue) + (1 if (compliance_score and compliance_score < 90) else 0)
    if evidence_signals >= 2:
        confidence = "High"
    elif evidence_signals == 1:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "probable_causes": probable_causes,
        "causal_chain": causal_chain,
        "contributing_factors": contributing_factors,
        "recommended_next_steps": [
            f"Dispatch technician to physically inspect {eq_id}",
            "Review last 72h sensor trend data for early anomaly signatures",
            "Check upstream and downstream equipment for correlated deviations",
        ],
        "confidence": confidence,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_root_cause(body: RCARequest, user: m.UserProfile = Depends(get_current_user)) -> RCAResponse:
    """
    Run a full root cause analysis on a reported symptom.
    Returns ranked probable causes, causal chain, and recommended actions.
    """
    if not body.symptom.strip():
        raise HTTPException(status_code=422, detail="symptom must not be empty")

    if body.equipment_id:
        eq = await db.get_equipment(body.equipment_id)
        if eq is None:
            raise HTTPException(status_code=404, detail=f"Equipment '{body.equipment_id}' not found")

    evidence = await _collect_evidence(body.equipment_id)

    # Try LLM first, fall back to heuristics
    result = await _llm_rca(body.symptom, body.equipment_id, evidence)
    analysis_source = "llm"
    if result is None:
        result = _heuristic_rca(body.symptom, body.equipment_id, evidence)
        analysis_source = "heuristic"

    return RCAResponse(
        event=body.symptom,
        equipment_id=body.equipment_id,
        analysis_timestamp=datetime.utcnow().isoformat() + "Z",
        probable_causes=[ProbableCause(**c) for c in result.get("probable_causes", [])],
        causal_chain=[CausalStep(**s) for s in result.get("causal_chain", [])],
        sensor_anomalies=evidence.get("sensor_anomalies", []),
        ml_sensor_anomalies=evidence.get("ml_sensor_anomalies", []),
        contributing_factors=result.get("contributing_factors", []),
        recommended_next_steps=result.get("recommended_next_steps", []),
        confidence=result.get("confidence", "Medium"),
        analysis_source=analysis_source,
    )


@router.get("/events")
async def list_quick_events():
    """
    Return quick-start RCA events built LIVE from the current DB state:
      1. Active sensor alarms   — equipment readings above alarm threshold
      2. Overdue maintenance    — equipment.maintenance_due_days <= 0
    Returns up to 8 events, sorted Critical → High → Medium.
    """
    events: list[dict] = []
    SEV_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

    # 1. Active sensor alarms ─────────────────────────────────────────────────
    all_eq = await db.get_all_equipment_list()
    for eq in all_eq:
        readings: dict = eq.get("current_readings") or {}
        for key, r in readings.items():
            if not isinstance(r, dict):
                continue
            val = r.get("value")
            if not is_in_alarm(val, r):
                continue
            alarm = r.get("alarm")
            direction = alarm_direction(r)
            excess_pct = round(abs(val - alarm) / alarm * 100) if alarm else 0
            label = key.replace("_", " ").title().replace(" De", " DE").replace(" Nde", " NDE")
            sev = "Critical" if is_in_trip(val, r) else "High"
            comparison = "dropped below" if direction == "low" else "exceeds"
            events.append({
                "id": f"alarm-{eq['id']}-{key}",
                "title": f"{eq['id']}: {label} alarm active",
                "description": (
                    f"{eq.get('name', eq['id'])} has an active {label} alarm. "
                    f"Current reading {val} {r.get('unit', '')} {comparison} alarm threshold "
                    f"{alarm} {r.get('unit', '')} by {excess_pct}%."
                ),
                "equipment_hint": eq["id"],
                "severity": sev,
            })

    # 2. Overdue maintenance ──────────────────────────────────────────────────
    for eq in all_eq:
        due = eq.get("maintenance_due_days")
        if due is not None and due <= 0:
            days_over = abs(due)
            events.append({
                "id": f"maint-{eq['id']}",
                "title": f"{eq['id']}: maintenance overdue {days_over}d",
                "description": (
                    f"{eq.get('name', eq['id'])} maintenance is overdue by {days_over} days. "
                    f"Investigate whether missed maintenance is contributing to equipment degradation."
                ),
                "equipment_hint": eq["id"],
                "severity": "High" if days_over > 14 else "Medium",
            })

    # Sort Critical → High → Medium, cap at 8
    events.sort(key=lambda x: SEV_ORDER.get(x.get("severity", "Low"), 9))
    return events[:8]
