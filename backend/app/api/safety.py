"""
AI Operations Brain — Safety & Permit-to-Work (PTW) Engine
Phase 9 of the IndustrialGPT vision: reads HAZOP entries, active permits,
and incident reports to warn about maintenance conflicts.

Endpoints:
  POST /api/v1/safety/check-conflict   — Check if an action conflicts with active PTW/HAZOP
  GET  /api/v1/safety/permits          — List active permits
  GET  /api/v1/safety/hazop/{equip_id} — HAZOP notes for equipment
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.kb_ingestion import on_safety_conflict, ingest_async

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Demo active permits ───────────────────────────────────────────────────────
# In production these would come from a PTW system (SAP PM, Maximo, etc.)

_today = date.today()

ACTIVE_PERMITS: list[dict[str, Any]] = [
    {
        "id": "PTW-2026-034",
        "type": "Hot Work",
        "class": "B",
        "description": "Welding and grinding on Feed Header pipe spool — Unit 4 CDU",
        "location": "Unit 4 — CDU, Feed Header, Grid B3",
        "equipment_proximity": ["P-101", "P-202", "V-301"],
        "issued_by": "S. Venkataraman",
        "issued_to": "Fabrication Team C",
        "valid_from": _today.isoformat(),
        "valid_until": (_today + timedelta(days=2)).isoformat(),
        "status": "Active",
        "risk_level": "High",
        "gas_test_required": True,
        "fire_watch_required": True,
        "conflict_radius_m": 15,
    },
    {
        "id": "PTW-2026-035",
        "type": "Confined Space Entry",
        "class": "A",
        "description": "Internal inspection of V-301 — Reflux Drum",
        "location": "Unit 4 — CDU, V-301 Reflux Drum",
        "equipment_proximity": ["V-301", "P-101"],
        "issued_by": "Priya Nair",
        "issued_to": "Inspection Team 2",
        "valid_from": _today.isoformat(),
        "valid_until": (_today + timedelta(days=1)).isoformat(),
        "status": "Active",
        "risk_level": "Critical",
        "continuous_gas_monitoring": True,
        "rescue_team_standby": True,
        "conflict_radius_m": 5,
    },
    {
        "id": "PTW-2026-031",
        "type": "Electrical Isolation",
        "class": "C",
        "description": "LOTO on MCC-4 Bus Section — Power isolation for Motor M-101",
        "location": "MCC Room 4, Panel 4B",
        "equipment_proximity": ["P-101"],
        "issued_by": "Electrical Supervisor",
        "issued_to": "Electrical Team A",
        "valid_from": (_today - timedelta(days=1)).isoformat(),
        "valid_until": (_today + timedelta(days=1)).isoformat(),
        "status": "Active",
        "risk_level": "High",
        "conflict_radius_m": 0,   # same equipment
    },
]

# ── HAZOP / Equipment safety notes ───────────────────────────────────────────

HAZOP_NOTES: dict[str, list[dict[str, Any]]] = {
    "P-101": [
        {
            "node": "P-101 Suction",
            "deviation": "No Flow",
            "cause": "Suction MOV-101A fails closed",
            "consequence": "Pump cavitation, rapid bearing failure, fire risk if seal fails",
            "safeguard": "Flow transmitter FT-101 with low-low trip; MOV-101A open confirmation",
            "risk_rating": "High",
            "action": "LOTO on MOV-101A and MOV-101B before any maintenance on P-101",
        },
        {
            "node": "P-101 Discharge",
            "deviation": "High Pressure",
            "cause": "Discharge MOV-101B fails closed with pump running",
            "consequence": "Overpressure on pump casing and seals, potential crude oil release",
            "safeguard": "Pressure safety valve PSV-101 set at 9.5 bar; auto-shutdown on high-high",
            "risk_rating": "Critical",
            "action": "Never close discharge valve with pump running. Verify PSV-101 free to operate.",
        },
        {
            "node": "P-101 Seal System",
            "deviation": "Seal Leakage",
            "cause": "Mechanical seal failure, O-ring degradation",
            "consequence": "Crude oil release to atmosphere — fire and environmental hazard",
            "safeguard": "Seal flush Plan 11; continuous CCTV monitoring; gas detector near pump",
            "risk_rating": "High",
            "action": "Ensure N2 purge after isolation before opening seal chamber. Use hot-work permit if crude is present.",
        },
    ],
    "P-202": [
        {
            "node": "P-202 Suction",
            "deviation": "Low NPSH",
            "cause": "High process temperature or low suction pressure",
            "consequence": "Cavitation — rapid impeller erosion and bearing failure",
            "safeguard": "NPSH margin interlock; speed reduction at low suction pressure",
            "risk_rating": "Medium",
            "action": "Verify suction conditions before starting. Operate below 85% BEP.",
        },
    ],
    "V-301": [
        {
            "node": "V-301 Vessel",
            "deviation": "Confined Space",
            "cause": "Hydrocarbon vapours from crude residue",
            "consequence": "Toxic / explosive atmosphere — fatal risk to personnel",
            "safeguard": "Continuous gas monitoring mandatory; rescue team standby; CSE permit class A",
            "risk_rating": "Critical",
            "action": "Class A CSE permit required. Gas-free certificate mandatory before entry. BA sets required.",
        },
    ],
    "HX-201": [
        {
            "node": "HX-201 Shell Side",
            "deviation": "High Pressure",
            "cause": "Tube leak — high-pressure crude leaks into lower-pressure steam side",
            "consequence": "Steam hammer, potential vessel rupture",
            "safeguard": "Differential pressure alarm; annual tube inspection per API 510",
            "risk_rating": "High",
            "action": "Depressurize both sides and vent before any maintenance. Verify blinds installed.",
        },
    ],
}

# ── Request schemas ───────────────────────────────────────────────────────────

class ConflictCheckRequest(BaseModel):
    equipment_id: str
    action: str                    # e.g. "Replace mechanical seal"
    planned_start: str | None = None   # ISO datetime string


class ConflictResult(BaseModel):
    conflicts: list[dict[str, Any]]
    hazop_notes: list[str]
    required_permits: list[str]
    clearance: str                 # CLEAR | CONDITIONAL | BLOCKED


# ── Conflict engine ───────────────────────────────────────────────────────────

def _find_conflicts(equipment_id: str, action: str) -> list[dict[str, Any]]:
    """Return all active permits that could conflict with this equipment/action."""
    action_l = action.lower()
    conflicts = []

    for permit in ACTIVE_PERMITS:
        if equipment_id not in permit.get("equipment_proximity", []):
            continue

        conflict = {
            "permit_id": permit["id"],
            "permit_type": permit["type"],
            "description": permit["description"],
            "location": permit["location"],
            "risk_level": permit["risk_level"],
            "valid_until": permit["valid_until"],
            "issued_to": permit["issued_to"],
            "conflict_reason": "",
            "resolution": "",
        }

        # Hot work near crude oil maintenance → fire risk
        if permit["type"] == "Hot Work" and any(
            kw in action_l for kw in ["seal", "bearing", "open", "dismantle", "remove", "replace"]
        ):
            conflict["conflict_reason"] = (
                "Hot work is active within 15m. Opening crude-wetted equipment during hot work "
                "creates an explosive/fire hazard."
            )
            conflict["resolution"] = (
                "Coordinate with hot work permit holder. Suspend hot work or wait until "
                "this maintenance is complete and area is gas-free."
            )

        # Confined space entry — nearby equipment isolation
        elif permit["type"] == "Confined Space Entry":
            conflict["conflict_reason"] = (
                "Confined space entry is in progress on adjacent equipment. "
                "Disturbance or vibration during maintenance could affect CSE safety."
            )
            conflict["resolution"] = (
                "Notify CSE permit holder before starting. Obtain written concurrence "
                "from area supervisor."
            )

        # Electrical isolation — same equipment
        elif permit["type"] == "Electrical Isolation":
            conflict["conflict_reason"] = (
                "Electrical isolation (LOTO) is active on motor M-101 associated with this pump. "
                "Verify LOTO covers your isolation requirements."
            )
            conflict["resolution"] = (
                "Confirm your LOTO is incorporated into the existing electrical isolation certificate. "
                "Do not re-energize without clearing all personal locks."
            )

        else:
            continue   # no conflict for this permit type

        conflicts.append(conflict)

    return conflicts


def _get_hazop_notes(equipment_id: str, action: str) -> list[str]:
    """Return relevant HAZOP notes for this equipment action."""
    notes_raw = HAZOP_NOTES.get(equipment_id, [])
    action_l = action.lower()
    relevant: list[str] = []

    for note in notes_raw:
        # Always include high/critical notes
        if note["risk_rating"] in ("Critical", "High"):
            relevant.append(f"[{note['risk_rating']}] {note['node']}: {note['action']}")
        # Include if deviation relates to the action keyword
        elif any(kw in action_l for kw in note["deviation"].lower().split()):
            relevant.append(f"[{note['risk_rating']}] {note['node']}: {note['action']}")

    return relevant


def _required_permits(equipment_id: str, action: str) -> list[str]:
    """Determine which new permits are needed for this action."""
    action_l = action.lower()
    permits: list[str] = []

    # All machinery maintenance
    permits.append("PTW Class C — Machinery (required for all corrective maintenance)")

    if any(kw in action_l for kw in ["weld", "grind", "cut", "flame", "hot"]):
        permits.append("PTW Class B — Hot Work (welding / grinding / flame cutting)")

    if any(kw in action_l for kw in ["entry", "inside", "vessel", "drum", "tank"]):
        permits.append("PTW Class A — Confined Space Entry")

    if any(kw in action_l for kw in ["electric", "motor", "cable", "power", "loto"]):
        permits.append("Electrical Isolation Certificate (LOTO)")

    if any(kw in action_l for kw in ["height", "scaffold", "elevated", "roof"]):
        permits.append("Work at Height Permit")

    if any(kw in action_l for kw in ["radiation", "ndt", "x-ray", "radiograph"]):
        permits.append("Radiation Work Permit")

    return permits


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/check-conflict")
async def check_conflict(body: ConflictCheckRequest) -> ConflictResult:
    """
    Check if a proposed maintenance action conflicts with active permits or HAZOP.
    Returns conflict details and clearance status.
    """
    conflicts = _find_conflicts(body.equipment_id, body.action)
    hazop_notes = _get_hazop_notes(body.equipment_id, body.action)
    required_permits = _required_permits(body.equipment_id, body.action)

    # Determine clearance
    high_risk = any(c["risk_level"] in ("Critical", "High") for c in conflicts)
    if any(c for c in conflicts if "fire" in c["conflict_reason"].lower() or "explosive" in c["conflict_reason"].lower()):
        clearance = "BLOCKED"
    elif conflicts or high_risk:
        clearance = "CONDITIONAL"
    else:
        clearance = "CLEAR"

    result = ConflictResult(
        conflicts=conflicts,
        hazop_notes=hazop_notes,
        required_permits=required_permits,
        clearance=clearance,
    )

    # ── KB: log this safety check so AI agents can reference it ──────────────
    if conflicts or clearance != "CLEAR":
        ingest_async(on_safety_conflict(
            equipment_id=body.equipment_id,
            action=body.action,
            conflicts=conflicts,
            hazop_notes=hazop_notes,
            clearance=clearance,
            required_permits=required_permits,
        ))

    return result


@router.get("/permits")
async def list_active_permits():
    """Return all currently active permits."""
    return {
        "count": len(ACTIVE_PERMITS),
        "permits": ACTIVE_PERMITS,
        "as_of": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/hazop/{equipment_id}")
async def get_hazop_notes(equipment_id: str):
    """Return HAZOP analysis notes for a specific piece of equipment."""
    notes = HAZOP_NOTES.get(equipment_id.upper(), [])
    return {
        "equipment_id": equipment_id,
        "hazop_count": len(notes),
        "notes": notes,
    }
