"""
@file db_test_data_model.py
@module backend

SUMMARY
-------
Reads the complete live dataset from PostgreSQL and:
  1. Prints a full snapshot of every table as clean Python dicts (console or file).
  2. Exposes a DataFactory class with factory methods for every entity type so
     you can generate arbitrarily more records that are consistent with the
     existing schema, IDs, and referential conventions.
  3. Provides a generate_bulk() helper that calls every factory and writes a
     ready-to-import Python module to test_data/generated_model.py.

USAGE
-----
# Print full DB snapshot to stdout
python db_test_data_model.py --dump

# Write snapshot + N extra records per entity to test_data/generated_model.py
python db_test_data_model.py --generate --count 5 --output test_data/generated_model.py

# Only write the generated extra rows (no snapshot)
python db_test_data_model.py --generate --count 10 --no-snapshot --output my_data.py

DEPENDENCIES
------------
- psycopg2-binary  (pip install psycopg2-binary)
- faker            (pip install faker)

@created 2026-07-22
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, date
from pathlib import Path
from pprint import pformat
from typing import Any

import psycopg2
import psycopg2.extras

try:
    from faker import Faker
    _fake = Faker("en_US")
    Faker.seed(42)
except ImportError:
    _fake = None  # type: ignore[assignment]

# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL connection (matches docker-compose defaults)
# ─────────────────────────────────────────────────────────────────────────────
DSN = "host=localhost port=5432 dbname=opsbrain user=opsbrain password=opsbrain2024"


def _connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(DSN, cursor_factory=psycopg2.extras.RealDictCursor)


def _q(conn, sql: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# SNAPSHOT — read every table
# ─────────────────────────────────────────────────────────────────────────────

def read_snapshot() -> dict[str, list[dict]]:
    """Return a dict mapping table_name → list of row dicts from the live DB."""
    conn = _connect()
    try:
        return {
            "equipment": _q(conn, "SELECT * FROM equipment ORDER BY id"),
            "incidents": _q(conn, "SELECT * FROM incidents ORDER BY id"),
            "maintenance_records": _q(conn, "SELECT * FROM maintenance_records ORDER BY id"),
            "documents": _q(conn, "SELECT * FROM documents ORDER BY id"),
            "compliance": _q(conn, "SELECT * FROM compliance ORDER BY equipment_id"),
            "spare_parts": _q(conn, "SELECT * FROM spare_parts ORDER BY id"),
            "technicians": _q(conn, "SELECT * FROM technicians ORDER BY id"),
            "sensor_history": _q(conn, "SELECT * FROM sensor_history ORDER BY equipment_id, sensor_key"),
            "graph_nodes": _q(conn, "SELECT * FROM graph_nodes ORDER BY id"),
            "graph_links": _q(conn, "SELECT * FROM graph_links ORDER BY id"),
            "projects": _q(conn, "SELECT * FROM projects ORDER BY id"),
            "plants": _q(conn, "SELECT * FROM plants ORDER BY id"),
            "user_profiles": _q(conn, "SELECT * FROM user_profiles ORDER BY id"),
            "permits_to_work": _q(conn, "SELECT * FROM permits_to_work ORDER BY id"),
            "safety_procedures": _q(conn, "SELECT * FROM safety_procedures ORDER BY id"),
            "managed_work_orders": _q(conn, "SELECT * FROM managed_work_orders ORDER BY id"),
            "incident_reports": _q(conn, "SELECT * FROM incident_reports ORDER BY id"),
            "quality_inspections": _q(conn, "SELECT * FROM quality_inspections ORDER BY id"),
            "action_items": _q(conn, "SELECT * FROM action_items ORDER BY id"),
            "saved_checklists": _q(conn, "SELECT * FROM saved_checklists ORDER BY id"),
            "saved_work_orders": _q(conn, "SELECT * FROM saved_work_orders ORDER BY id"),
            "drawings": _q(conn, "SELECT * FROM drawings ORDER BY id"),
            "audit_logs": _q(conn, "SELECT * FROM audit_logs ORDER BY id LIMIT 50"),
            "integration_configs": _q(conn, "SELECT * FROM integration_configs ORDER BY id"),
            "custom_dashboards": _q(conn, "SELECT * FROM custom_dashboards ORDER BY id"),
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# REFERENCE DATA extracted from the live snapshot
# (used by DataFactory as valid FK pool)
# ─────────────────────────────────────────────────────────────────────────────

#: Static reference pools — populated lazily from the DB snapshot
_REF: dict[str, list[Any]] = {}


def _load_refs(snap: dict[str, list[dict]]) -> None:
    _REF["equipment_ids"] = [r["id"] for r in snap["equipment"]]
    _REF["user_ids"] = [r["id"] for r in snap["user_profiles"]]
    _REF["user_names"] = {r["id"]: r["name"] for r in snap["user_profiles"]}
    _REF["user_roles"] = {r["id"]: r["role"] for r in snap["user_profiles"]}
    _REF["project_ids"] = [r["id"] for r in snap["projects"]]
    _REF["plant_ids"] = [r["id"] for r in snap["plants"]]
    _REF["permit_ids"] = [r["id"] for r in snap["permits_to_work"]]
    _REF["mwo_ids"] = [r["id"] for r in snap["managed_work_orders"]]
    _REF["procedure_ids"] = [r["id"] for r in snap["safety_procedures"]]


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _now(offset_days: int = 0) -> str:
    return (datetime.utcnow() + timedelta(days=offset_days)).isoformat(timespec="seconds")


def _date(offset_days: int = 0) -> str:
    return (date.today() + timedelta(days=offset_days)).isoformat()


def _pick(pool: list) -> Any:
    return random.choice(pool) if pool else None


def _fake_name() -> str:
    return _fake.name() if _fake else f"User {random.randint(100, 999)}"


def _fake_sentence(nb_words: int = 10) -> str:
    return _fake.sentence(nb_words=nb_words) if _fake else f"Auto-generated text {uuid.uuid4().hex[:6]}"


# ─────────────────────────────────────────────────────────────────────────────
# DATA FACTORY
# ─────────────────────────────────────────────────────────────────────────────

class DataFactory:
    """
    Factory that generates new records consistent with the live DB schema.

    Every method returns a plain dict that maps 1:1 to the SQLAlchemy model
    / PostgreSQL table.  Pass the output directly to the API or the seed
    functions in db_service.py / project_seed.py.

    Example
    -------
    >>> snap = read_snapshot()
    >>> f = DataFactory(snap)
    >>> new_equipment = f.equipment()
    >>> new_permit    = f.permit_to_work()
    >>> bulk          = f.bulk(n=10)
    """

    # ── Enum pools ────────────────────────────────────────────────────────────
    EQUIPMENT_TYPES = ["Centrifugal Pump", "Heat Exchanger", "Compressor", "Pressure Vessel",
                       "Fan", "Motor", "Valve", "Column", "Reactor", "Separator"]
    EQUIPMENT_LOCATIONS = ["Unit 4 — CDU", "Unit 5 — VDU", "Unit 6 — HDS", "Unit 7 — FCC",
                           "Utilities Block A", "Utilities Block B", "Flare Area", "Tank Farm"]
    CRITICALITIES = ["Critical", "High", "Medium", "Low"]
    EQUIP_STATUSES = ["Running", "Running — Alert", "Standby", "Shutdown", "Under Maintenance"]

    INCIDENT_SEVERITIES = ["P1", "P2", "P3", "P4", "P5", "Critical", "High", "Medium", "Low"]
    INCIDENT_CATEGORIES = ["Bearing", "Seal", "Cavitation", "Electrical", "Instrumentation",
                           "Process", "Structural", "Corrosion", "Fatigue", "Human Error"]
    MR_TYPES = ["Preventive", "Corrective", "Predictive", "Emergency"]
    MR_STATUSES = ["Completed", "In Progress", "Pending", "Overdue", "Cancelled"]

    DOC_TYPES = ["manual", "sop", "incident_report", "slack_comms", "email_comms", "drawing", "other"]

    PERMIT_TYPES = ["hot_work", "cold_work", "confined_space", "electrical_isolation",
                    "height", "radiography", "excavation"]
    PERMIT_STATUSES = ["draft", "submitted", "area_authority_review", "safety_review",
                       "ap_approval", "issued", "active", "suspended",
                       "completion_requested", "closed", "cancelled"]
    AREA_CLASSIFICATIONS = ["Zone 0 — Ex ia", "Zone 1 — Ex d / Ex e", "Zone 2 — Ex n",
                             "Non-hazardous", "Classified — Div 2"]

    PROCEDURE_DOC_TYPES = ["SOP", "JSA", "SWMS", "MSDS", "ERP", "Checklist", "Work_Instruction"]
    PROCEDURE_CATEGORIES = ["Mechanical", "Electrical", "Process", "Civil", "Safety", "Instrumentation"]
    PROCEDURE_STATUSES = ["draft", "peer_review", "technical_review", "final_approval", "active", "obsolete"]

    MWO_CATEGORIES = ["preventive", "corrective", "predictive", "emergency", "shutdown", "modification"]
    MWO_PRIORITIES = ["low", "medium", "high", "critical"]
    MWO_STATUSES = ["draft", "submitted", "approved", "scheduled", "in_progress",
                    "pending_verification", "verified", "closed"]

    INCIDENT_REPORT_TYPES = ["near_miss", "first_aid", "medical_treatment", "lost_time",
                              "fatality", "environmental", "property_damage", "fire", "spill"]
    INCIDENT_REPORT_STATUSES = ["reported", "investigation", "root_cause_analysis", "capa", "closed"]

    INSPECTION_TYPES = ["equipment", "process", "safety_audit", "environmental", "contractor", "pre_startup"]
    INSPECTION_STATUSES = ["scheduled", "in_progress", "completed", "failed", "cancelled", "closed_with_findings"]

    ACTION_TYPES = ["corrective", "preventive", "improvement", "observation"]
    ACTION_STATUSES = ["open", "in_progress", "completed", "overdue", "cancelled"]
    ACTION_PRIORITIES = ["low", "medium", "high", "critical"]

    USER_ROLES = ["technician", "supervisor", "safety_officer", "area_authority",
                  "authorized_person", "manager", "quality_inspector"]
    DEPARTMENTS = ["Maintenance", "Operations", "HSE", "Engineering", "Quality",
                   "Projects", "Instrument", "Electrical"]

    PROJECT_TYPES = ["Industrial", "Shutdown", "Turnaround", "Modification", "Greenfield"]
    PROJECT_PHASES = ["Planning", "Execution", "Operations", "Closed"]
    PLANT_TYPES = ["Process Unit", "Utilities", "Offsites", "Control Room", "Tankage"]

    HAZARDS = [
        {"hazard": "Hydrocarbon vapour ignition", "likelihood": "Medium", "severity": "Critical",
         "mitigation": "Continuous gas monitoring, fire watch, hot work barriers"},
        {"hazard": "H2S exposure", "likelihood": "Low", "severity": "Critical",
         "mitigation": "H2S monitor, SCBA, buddy system"},
        {"hazard": "Struck by rotating equipment", "likelihood": "Low", "severity": "High",
         "mitigation": "Guard in place, LOTO, machine stopped before inspection"},
        {"hazard": "Burns from hot surfaces", "likelihood": "Medium", "severity": "Medium",
         "mitigation": "Insulated gloves, heat-resistant coverall, hot surface signs"},
        {"hazard": "Fall from height", "likelihood": "Medium", "severity": "High",
         "mitigation": "Full body harness, lifeline, edge protection"},
        {"hazard": "Oxygen deficiency in vessel", "likelihood": "High", "severity": "Critical",
         "mitigation": "Continuous O2 monitoring, ventilation, SCBA"},
        {"hazard": "Chemical splash", "likelihood": "Low", "severity": "Medium",
         "mitigation": "Chemical goggles, chemical-resistant gloves"},
        {"hazard": "Noise above 85 dB(A)", "likelihood": "High", "severity": "Low",
         "mitigation": "Ear defenders (SNR 27), limit exposure time"},
        {"hazard": "Pressurised line opening", "likelihood": "Low", "severity": "Critical",
         "mitigation": "Depressurise and vent prior to breaking, blind flange"},
        {"hazard": "Electrical shock — live equipment", "likelihood": "Low", "severity": "Critical",
         "mitigation": "LOTO, zero-energy verification, insulated tools"},
    ]

    PPE = [
        {"item": "FR coverall", "specification": "EN ISO 11612 Level A1 B1 C1"},
        {"item": "Safety helmet", "specification": "EN 397, class P"},
        {"item": "Safety boots", "specification": "EN ISO 20345 S3"},
        {"item": "Chemical splash goggles", "specification": "EN 166 1B 3 4"},
        {"item": "Nitrile gloves", "specification": "EN 374 Type B, AQL 1.5"},
        {"item": "Welding gloves", "specification": "EN 12477 Type A"},
        {"item": "SCBA", "specification": "EN 137 positive pressure"},
        {"item": "Ear defenders", "specification": "EN 352-1, SNR 27"},
        {"item": "Full body harness", "specification": "EN 361 + EN 354 lanyard"},
        {"item": "Auto-darkening welding helmet", "specification": "EN 379 Shade 10"},
    ]

    PROCEDURE_STEPS_TEMPLATES = [
        {"title": "Pre-task safety briefing", "description": "Brief all workers on task scope, hazards, controls, and emergency procedure. Sign TBT form.", "responsible_role": "supervisor"},
        {"title": "Isolation and LOTO", "description": "Apply all energy isolations per isolation register. Verify zero energy state.", "responsible_role": "authorized_person"},
        {"title": "PPE inspection", "description": "Confirm all PPE is correct grade, undamaged, and fitted properly.", "responsible_role": "technician"},
        {"title": "Gas test", "description": "Measure LEL, O2, and H2S at work point. Document results.", "responsible_role": "safety_officer"},
        {"title": "Carry out work", "description": "Perform maintenance task per manufacturer's instructions and work order.", "responsible_role": "technician"},
        {"title": "Quality check", "description": "Inspect work completed. Measure clearances, torques, and alignment as applicable.", "responsible_role": "supervisor"},
        {"title": "Reinstate and commission", "description": "Remove isolations in reverse order. Pressurise slowly. Check for leaks.", "responsible_role": "technician"},
        {"title": "Close out and sign off", "description": "Complete work order. Return tools. Update CMMS. Notify operations.", "responsible_role": "supervisor"},
    ]

    CORRECTIVE_ACTIONS = [
        "Replace worn bearing with OEM equivalent. Grease to manufacturer's specification.",
        "Repair mechanical seal assembly. Install upgraded Type-2 double seal.",
        "Flush and replace hydraulic oil. Check filter delta-P after 24 hours.",
        "Perform laser alignment. Acceptable tolerance <0.05 mm offset.",
        "Replace inlet filter element. Record differential pressure at commissioning.",
        "Inspect impeller for erosion. Coat with Stellite if <15% material loss.",
        "Install vibration baseline data card on equipment tag. Program DCS alarm.",
        "Torque all flange bolts to specification per flange table. Leak test 1.1× MAWP.",
        "Clean and re-calibrate instrument transmitter. Verify against reference gauge.",
        "Renew insulation on pipe section. Repair cladding and moisture barrier.",
    ]

    def __init__(self, snapshot: dict[str, list[dict]]) -> None:
        _load_refs(snapshot)
        self.snap = snapshot
        # Running counters for unique IDs
        self._eq_n = 100
        self._inc_n = 2000
        self._mr_n = 5000
        self._doc_n = 500
        self._ptw_n = 1000
        self._proc_n = 500
        self._mwo_n = 2000
        self._ir_n = 500
        self._qi_n = 500
        self._ai_n = 500
        self._usr_n = 100
        self._prj_n = 100
        self._plt_n = 100

    # ── Equipment ─────────────────────────────────────────────────────────────
    def equipment(self) -> dict:
        eq_type = _pick(self.EQUIPMENT_TYPES)
        tag = f"EQ-{self._eq_n:04d}"
        self._eq_n += 1
        hs = random.randint(40, 100)
        return {
            "id": tag,
            "name": f"{eq_type} — {tag}",
            "type": eq_type,
            "location": _pick(self.EQUIPMENT_LOCATIONS),
            "health_score": hs,
            "failure_probability": max(0, round((100 - hs) * random.uniform(0.2, 0.6), 1)),
            "compliance_score": random.randint(70, 100),
            "maintenance_due_days": random.randint(-5, 90),
            "criticality": _pick(self.CRITICALITIES),
            "status": _pick(self.EQUIP_STATUSES),
            "manufacturer": _pick(["Flowserve", "KSB", "Sulzer", "Atlas Copco", "GEA", "ALFA LAVAL", "Siemens"]),
            "model": f"MDL-{random.randint(100, 999)}",
            "installed_date": _date(-random.randint(365, 4000)),
            "technicians": random.sample([n for n in _REF.get("user_names", {}).values()], k=min(2, len(_REF.get("user_names", {})))),
            "current_readings": {
                "vibration_de": {"value": round(random.uniform(1.5, 9.0), 1), "unit": "mm/s", "normal": 4.5, "alarm": 7.1, "trip": 11.2},
                "bearing_temp_de": {"value": round(random.uniform(45, 85), 1), "unit": "°C", "normal": 55, "alarm": 75, "trip": 90},
            },
            "downstream_equipment": random.sample(_REF.get("equipment_ids", []), k=min(1, len(_REF.get("equipment_ids", [])))),
            "specifications": {
                "rated_flow": f"{random.randint(50, 500)} m³/hr",
                "motor_power": f"{random.randint(15, 200)} kW",
                "rated_rpm": str(random.choice([960, 1480, 2960])),
            },
            "extra": {},
            "discovered": False,
            "manually_registered": True,
            "source_documents": [],
            "created_at": datetime.utcnow().isoformat(),
        }

    # ── Incidents (legacy) ────────────────────────────────────────────────────
    def incident(self, equipment_id: str | None = None) -> dict:
        eq_id = equipment_id or _pick(_REF.get("equipment_ids", ["P-101"]))
        n = self._inc_n; self._inc_n += 1
        sev = _pick(["P3", "P4", "Medium", "High"])
        category = _pick(self.INCIDENT_CATEGORIES)
        return {
            "id": f"INC-GEN-{n:05d}",
            "equipment_id": eq_id,
            "date": _date(-random.randint(1, 730)),
            "title": f"{category} issue on {eq_id}",
            "severity": sev,
            "symptom": _fake_sentence(12) if _fake else f"Abnormal reading on {eq_id}",
            "root_cause": _fake_sentence(10) if _fake else f"Root cause — {category}",
            "root_cause_category": category,
            "action_taken": _pick(self.CORRECTIVE_ACTIONS),
            "lessons_learned": _fake_sentence(15) if _fake else "Preventive schedule updated.",
            "downtime_hours": random.randint(1, 48),
            "cost_usd": round(random.uniform(500, 50000), 2),
            "technician": _pick(list(_REF.get("user_names", {}).values())),
            "keywords": [category.lower(), eq_id.lower(), "generated"],
            "extra": {},
        }

    # ── Maintenance Records ───────────────────────────────────────────────────
    def maintenance_record(self, equipment_id: str | None = None) -> dict:
        eq_id = equipment_id or _pick(_REF.get("equipment_ids", ["P-101"]))
        n = self._mr_n; self._mr_n += 1
        mr_type = _pick(self.MR_TYPES)
        return {
            "id": f"MR-GEN-{n:06d}",
            "equipment_id": eq_id,
            "date": _date(-random.randint(0, 180)),
            "scheduled_date": _date(-random.randint(5, 185)),
            "type": mr_type,
            "description": f"{mr_type} maintenance on {eq_id} — generated record",
            "status": _pick(["Completed", "Completed", "Completed", "Overdue", "In Progress"]),
            "findings": _pick(self.CORRECTIVE_ACTIONS),
            "technician": _pick(list(_REF.get("user_names", {}).values())),
            "overdue_days": random.randint(0, 30) if random.random() < 0.15 else None,
            "extra": {},
        }

    # ── Documents ─────────────────────────────────────────────────────────────
    def document(self) -> dict:
        n = self._doc_n; self._doc_n += 1
        doc_type = _pick(self.DOC_TYPES)
        eq_ids = random.sample(_REF.get("equipment_ids", ["P-101"]), k=random.randint(1, 2))
        return {
            "id": f"DOC-GEN-{n:04d}",
            "name": f"Generated {doc_type.upper()} — {n:04d}",
            "type": doc_type,
            "equipment_ids": eq_ids,
            "date": _date(-random.randint(0, 365)),
            "sections": {"1": _fake_sentence(20) if _fake else "Section content"},
            "status": "processed",
            "pipeline_steps": {"extract": "done", "embed": "done", "classify": "done"},
            "entities": {"equipment": eq_ids},
            "file_path": None,
            "char_count": random.randint(500, 5000),
            "current_step": None,
            "extra": {},
        }

    # ── Compliance ────────────────────────────────────────────────────────────
    def compliance(self, equipment_id: str | None = None) -> dict:
        eq_id = equipment_id or _pick(_REF.get("equipment_ids", ["P-101"]))
        score = random.randint(60, 100)
        status = "Compliant" if score >= 90 else ("Warning" if score >= 70 else "Non-Compliant")
        issues = []
        if score < 90:
            issues.append({"id": f"CI-{random.randint(100,999)}", "type": _pick(["PM Overdue", "Calibration Due", "Inspection Overdue"]), "severity": "Warning"})
        return {
            "equipment_id": eq_id,
            "overall_score": score,
            "status": status,
            "issues": issues,
            "passed": ["Last PM within schedule" if score >= 90 else "Fire protection check OK"],
        }

    # ── Spare Parts ───────────────────────────────────────────────────────────
    def spare_part(self) -> dict:
        eq_ids = random.sample(_REF.get("equipment_ids", ["P-101"]), k=random.randint(1, 2))
        qty = random.randint(0, 20)
        reorder = random.randint(2, 5)
        status = "Out of Stock" if qty == 0 else ("Low Stock" if qty <= reorder else "Available")
        return {
            "id": _uid("SP"),
            "name": _pick(["Bearing 6311", "Mechanical Seal Type-2", "Gasket RF 6in", "Impeller", "Coupling Insert", "Filter Element", "O-Ring Kit", "Shaft Sleeve"]),
            "equipment_ids": eq_ids,
            "part_number": f"PN-{random.randint(10000, 99999)}",
            "quantity_on_hand": qty,
            "reorder_point": reorder,
            "lead_time_days": random.randint(5, 45),
            "location": f"Warehouse {_pick(['A', 'B', 'C'])}-{random.randint(1, 20):02d}",
            "unit_cost_usd": round(random.uniform(50, 5000), 2),
            "status": status,
        }

    # ── User Profile ─────────────────────────────────────────────────────────
    def user_profile(self) -> dict:
        n = self._usr_n; self._usr_n += 1
        name = _fake_name()
        first, *last_parts = name.split()
        last = last_parts[-1] if last_parts else "User"
        role = _pick(self.USER_ROLES)
        dept = _pick(self.DEPARTMENTS)
        return {
            "id": f"USR-GEN-{n:03d}",
            "employee_id": f"EMP-GEN-{n:03d}",
            "name": name,
            "email": f"{first.lower()}.{last.lower()}@plant.com",
            "department": dept,
            "role": role,
            "certifications": random.sample(["NEBOSH GC", "IOSH", "CSWIP 3.1", "BOSIET", "PMP", "ISO 9001", "HAZOP Leader", "Electrical AP"], k=random.randint(1, 3)),
            "plant_ids": random.sample(_REF.get("plant_ids", []), k=min(2, len(_REF.get("plant_ids", [])))),
            "is_active": True,
            "extra": {},
            "created_at": datetime.utcnow().isoformat(),
        }

    # ── Project ───────────────────────────────────────────────────────────────
    def project(self) -> dict:
        n = self._prj_n; self._prj_n += 1
        ptype = _pick(self.PROJECT_TYPES)
        mgr = _pick(_REF.get("user_ids", ["USR-006"]))
        now = datetime.utcnow()
        return {
            "id": f"PRJ-GEN-{n:03d}",
            "code": f"PROJ-GEN-{n:03d}",
            "name": f"Generated {ptype} Project {n:03d}",
            "description": _fake_sentence(15) if _fake else f"Project {n:03d} description",
            "type": ptype,
            "phase": _pick(self.PROJECT_PHASES),
            "status": _pick(["Active", "Active", "Active", "On-Hold", "Closed"]),
            "location": _pick(["Houston, TX", "Jubail, KSA", "Rotterdam, NL", "Mumbai, IN", "Aberdeen, UK"]),
            "plant_ids": random.sample(_REF.get("plant_ids", []), k=min(2, len(_REF.get("plant_ids", [])))),
            "equipment_ids": random.sample(_REF.get("equipment_ids", []), k=min(3, len(_REF.get("equipment_ids", [])))),
            "manager_id": mgr,
            "start_date": _date(-random.randint(30, 1000)),
            "end_date": _date(random.randint(30, 365)) if random.random() > 0.5 else None,
            "tags": random.sample(["refinery", "turnaround", "shutdown", "maintenance", "capital"], k=2),
            "extra": {},
            "created_by": mgr,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    # ── Plant ─────────────────────────────────────────────────────────────────
    def plant(self) -> dict:
        n = self._plt_n; self._plt_n += 1
        ptype = _pick(self.PLANT_TYPES)
        prj = _pick(_REF.get("project_ids", ["PRJ-DEMO-001"]))
        eq_ids = random.sample(_REF.get("equipment_ids", []), k=min(3, len(_REF.get("equipment_ids", []))))
        return {
            "id": f"PLT-GEN-{n:03d}",
            "code": f"PLT-GEN-{n:03d}",
            "name": f"Generated {ptype} {n:03d}",
            "project_id": prj,
            "type": ptype,
            "location": f"Block {_pick('ABCDEF')}, Row {random.randint(1, 10)}",
            "area": f"{_pick(['North', 'South', 'East', 'West'])} Plot",
            "description": _fake_sentence(12) if _fake else f"Plant {n:03d} description",
            "equipment_ids": eq_ids,
            "status": _pick(["Operational", "Operational", "Operational", "Shutdown", "Mothballed"]),
            "responsible_person_id": _pick(_REF.get("user_ids", ["USR-004"])),
            "extra": {},
            "created_at": datetime.utcnow().isoformat(),
        }

    # ── Permit to Work ────────────────────────────────────────────────────────
    def permit_to_work(self) -> dict:
        n = self._ptw_n; self._ptw_n += 1
        ptw_type = _pick(self.PERMIT_TYPES)
        originator = _pick(_REF.get("user_ids", ["USR-001"]))
        aa = _pick([uid for uid, role in _REF.get("user_roles", {}).items() if role == "area_authority"] or _REF.get("user_ids", ["USR-004"]))
        so = _pick([uid for uid, role in _REF.get("user_roles", {}).items() if role == "safety_officer"] or _REF.get("user_ids", ["USR-003"]))
        ap = _pick([uid for uid, role in _REF.get("user_roles", {}).items() if role == "authorized_person"] or _REF.get("user_ids", ["USR-005"]))
        eq_ids = random.sample(_REF.get("equipment_ids", ["P-101"]), k=random.randint(1, 2))
        start_dt = datetime.utcnow() + timedelta(days=random.randint(1, 14))
        end_dt = start_dt + timedelta(hours=random.randint(4, 12))
        status = _pick(self.PERMIT_STATUSES)
        hazards = random.sample(self.HAZARDS, k=random.randint(2, 4))
        ppe = random.sample(self.PPE, k=random.randint(3, 5))
        return {
            "id": f"PTW-GEN-{n:04d}",
            "permit_number": f"PTW-{datetime.utcnow().year}-{n:04d}",
            "permit_type": ptw_type,
            "title": f"{ptw_type.replace('_', ' ').title()} permit — {_pick(eq_ids)}",
            "scope_of_work": _fake_sentence(20) if _fake else f"Carry out {ptw_type} work on equipment.",
            "project_id": _pick(_REF.get("project_ids", ["PRJ-DEMO-001"])),
            "plant_id": _pick(_REF.get("plant_ids", ["PLT-DEMO-CDU"])),
            "equipment_ids": eq_ids,
            "location_description": f"Area {_pick('ABCDE')}, Grid {_pick('FGHJKL')}-{random.randint(1, 20):02d}",
            "area_classification": _pick(self.AREA_CLASSIFICATIONS),
            "planned_start": start_dt.isoformat(timespec="seconds"),
            "planned_end": end_dt.isoformat(timespec="seconds"),
            "actual_start": start_dt.isoformat(timespec="seconds") if status in ("active", "suspended", "completion_requested", "closed") else None,
            "actual_end": end_dt.isoformat(timespec="seconds") if status == "closed" else None,
            "status": status,
            "hazards": hazards,
            "ppe_requirements": ppe,
            "isolation_points": [
                {"tag_number": f"XV-{random.randint(1000,9999)}", "description": f"Isolation valve on {eq_ids[0]}", "isolation_type": _pick(["closed_locked", "LOTO", "blind_flange"]), "verified_by": aa, "verified_at": _now(-1)}
            ],
            "gas_tests": [
                {"tested_by": _REF.get("user_names", {}).get(so, "Safety Officer"), "test_time": _now(), "gas": "Hydrocarbon (LEL)", "result": "pass", "ppm": None, "lel_percent": 0.0}
            ] if ptw_type in ("hot_work", "confined_space") else [],
            "simops_conflicts": [],
            "emergency_response_ref": f"ERP-{_pick(['CDU', 'VDU', 'UTL'])}-{random.randint(1, 5):03d}",
            "work_order_id": _pick(_REF.get("mwo_ids")) if _REF.get("mwo_ids") else None,
            "originator_id": originator,
            "originator_name": _REF.get("user_names", {}).get(originator, ""),
            "originator_date": _now(-random.randint(2, 7)),
            "originator_comments": "Permit raised per maintenance schedule.",
            "area_authority_id": aa,
            "area_authority_name": _REF.get("user_names", {}).get(aa, ""),
            "area_authority_decision": "approved" if status not in ("draft", "submitted") else None,
            "area_authority_comments": "Equipment isolated and scope confirmed." if status not in ("draft", "submitted") else None,
            "area_authority_date": _now(-2) if status not in ("draft", "submitted") else None,
            "safety_officer_id": so,
            "safety_officer_name": _REF.get("user_names", {}).get(so, ""),
            "safety_officer_decision": "approved" if status in ("ap_approval", "issued", "active", "suspended", "completion_requested", "closed") else None,
            "safety_officer_comments": "JSA reviewed and signed." if status in ("ap_approval", "issued", "active", "closed") else None,
            "safety_officer_date": _now(-1) if status in ("ap_approval", "issued", "active", "closed") else None,
            "ap_id": ap,
            "ap_name": _REF.get("user_names", {}).get(ap, ""),
            "ap_decision": "issued" if status in ("issued", "active", "closed") else None,
            "ap_comments": "All isolations verified." if status in ("issued", "active", "closed") else None,
            "ap_issue_date": _now() if status in ("issued", "active", "closed") else None,
            "closure_requested_by": None,
            "closure_requested_at": None,
            "closure_comments": None,
            "audit_trail": [
                {"timestamp": _now(-5), "action": "created", "user": _REF.get("user_names", {}).get(originator, ""), "comments": ""},
                {"timestamp": _now(-4), "action": "submitted", "user": _REF.get("user_names", {}).get(originator, ""), "comments": ""},
            ],
            "created_by": originator,
            "created_at": _now(-5),
            "updated_at": _now(),
        }

    # ── Safety Procedure ──────────────────────────────────────────────────────
    def safety_procedure(self) -> dict:
        n = self._proc_n; self._proc_n += 1
        doc_type = _pick(self.PROCEDURE_DOC_TYPES)
        category = _pick(self.PROCEDURE_CATEGORIES)
        author = _pick(_REF.get("user_ids", ["USR-001"]))
        approver = _pick([uid for uid, role in _REF.get("user_roles", {}).items() if role in ("safety_officer", "manager")] or _REF.get("user_ids", ["USR-003"]))
        status = _pick(self.PROCEDURE_STATUSES)
        steps = [
            {**tmpl, "step_number": i + 1, "hazards": [], "controls": []}
            for i, tmpl in enumerate(random.sample(self.PROCEDURE_STEPS_TEMPLATES, k=random.randint(4, 7)))
        ]
        eq_ids = random.sample(_REF.get("equipment_ids", ["P-101"]), k=random.randint(1, 2))
        return {
            "id": f"SP-GEN-{n:04d}",
            "code": f"{doc_type}-GEN-{n:04d}",
            "title": f"Generated {doc_type} — {category} ({n:04d})",
            "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}",
            "doc_type": doc_type,
            "category": category,
            "project_id": _pick(_REF.get("project_ids", ["PRJ-DEMO-001"])),
            "plant_id": _pick(_REF.get("plant_ids") + [None]),
            "equipment_ids": eq_ids,
            "steps": steps,
            "hazard_register": random.sample([
                {"hazard": h["hazard"], "risk_before": "High", "risk_after": "Low", "control_measure": h["mitigation"]}
                for h in self.HAZARDS
            ], k=random.randint(1, 3)),
            "ppe_requirements": [p["item"] for p in random.sample(self.PPE, k=3)],
            "tools_required": random.sample(["Torque wrench", "Vibration meter", "IR thermometer", "Gas detector", "Pressure gauge", "Laser alignment tool"], k=2),
            "references": [f"API {random.choice([610, 650, 660, 674, 675])} {random.choice(['Pumps', 'Storage Tanks', 'Heat Exchangers'])}"],
            "tags": [category.lower(), doc_type.lower()],
            "risk_level": _pick(["Low", "Medium", "High", "Critical"]),
            "status": status,
            "author_id": author,
            "author_name": _REF.get("user_names", {}).get(author, ""),
            "authored_date": _date(-random.randint(30, 365)),
            "peer_reviewer_id": None,
            "peer_reviewer_name": None,
            "peer_review_decision": "approved" if status not in ("draft",) else None,
            "peer_review_comments": None,
            "peer_review_date": _date(-20) if status not in ("draft",) else None,
            "tech_reviewer_id": None,
            "tech_reviewer_name": None,
            "tech_review_decision": "approved" if status in ("final_approval", "active") else None,
            "tech_review_comments": None,
            "tech_review_date": _date(-10) if status in ("final_approval", "active") else None,
            "approver_id": approver if status == "active" else None,
            "approver_name": _REF.get("user_names", {}).get(approver, "") if status == "active" else None,
            "approver_decision": "approved" if status == "active" else None,
            "approver_comments": None,
            "approval_date": _date(-5) if status == "active" else None,
            "effective_date": _date(-3) if status == "active" else None,
            "review_due_date": _date(730) if status == "active" else None,
            "audit_trail": [{"timestamp": _now(-30), "action": "created", "user": _REF.get("user_names", {}).get(author, ""), "comments": ""}],
            "created_at": _now(-30),
            "updated_at": _now(),
        }

    # ── Managed Work Order ────────────────────────────────────────────────────
    def managed_work_order(self, equipment_id: str | None = None) -> dict:
        n = self._mwo_n; self._mwo_n += 1
        eq_id = equipment_id or _pick(_REF.get("equipment_ids", ["P-101"]))
        category = _pick(self.MWO_CATEGORIES)
        priority = _pick(self.MWO_PRIORITIES)
        status = _pick(self.MWO_STATUSES)
        creator = _pick(_REF.get("user_ids", ["USR-001"]))
        approver = _pick([uid for uid in _REF.get("user_ids", []) if uid != creator] or ["USR-002"])
        sched_start = datetime.utcnow() + timedelta(days=random.randint(-5, 14))
        sched_end = sched_start + timedelta(hours=random.randint(2, 24))
        tasks = [
            {"seq": i + 1, "title": step["title"], "description": step["description"],
             "trade": _pick(["Mechanical", "Electrical", "Process", "Inspection"]),
             "estimated_hours": round(random.uniform(0.5, 4), 1), "status": "pending", "notes": ""}
            for i, step in enumerate(random.sample(self.PROCEDURE_STEPS_TEMPLATES, k=random.randint(3, 6)))
        ]
        return {
            "id": f"MWO-GEN-{n:05d}",
            "wo_number": f"WO-GEN-{n:05d}",
            "title": f"{category.title()} WO — {eq_id} ({n:05d})",
            "description": _pick(self.CORRECTIVE_ACTIONS),
            "category": category,
            "priority": priority,
            "status": status,
            "project_id": _pick(_REF.get("project_ids", ["PRJ-DEMO-001"])),
            "plant_id": _pick(_REF.get("plant_ids", ["PLT-DEMO-CDU"])),
            "equipment_ids": [eq_id],
            "permit_id": _pick(_REF.get("permit_ids") + [None]),
            "scheduled_start": sched_start.isoformat(timespec="seconds"),
            "scheduled_end": sched_end.isoformat(timespec="seconds"),
            "actual_start": sched_start.isoformat(timespec="seconds") if status in ("in_progress", "pending_verification", "verified", "closed") else None,
            "actual_end": sched_end.isoformat(timespec="seconds") if status in ("verified", "closed") else None,
            "estimated_hours": round(random.uniform(2, 24), 1),
            "actual_hours": round(random.uniform(2, 28), 1) if status in ("verified", "closed") else None,
            "tasks": tasks,
            "materials": [{"part_number": f"PN-{random.randint(10000,99999)}", "description": "Consumable", "qty_required": random.randint(1, 5), "qty_issued": random.randint(0, 5), "unit": "ea"}],
            "safety_requirements": [f"Permit required: {_pick(self.PERMIT_TYPES).replace('_', ' ').title()}"],
            "created_by_id": creator,
            "created_by_name": _REF.get("user_names", {}).get(creator, ""),
            "created_at": _now(-random.randint(1, 14)),
            "approver_id": approver,
            "approver_name": _REF.get("user_names", {}).get(approver, ""),
            "approval_decision": "approved" if status not in ("draft", "submitted") else None,
            "approval_comments": None,
            "approval_date": _now(-random.randint(1, 5)) if status not in ("draft", "submitted") else None,
            "verifier_id": None,
            "verifier_name": None,
            "verification_decision": None,
            "verification_comments": None,
            "verification_date": None,
            "completed_by_id": None,
            "completed_by_name": None,
            "completion_date": None,
            "completion_notes": None,
            "audit_trail": [
                {"timestamp": _now(-7), "action": "created", "user": _REF.get("user_names", {}).get(creator, ""), "comments": ""},
            ],
            "updated_at": _now(),
        }

    # ── Incident Report (formal) ──────────────────────────────────────────────
    def incident_report(self, equipment_id: str | None = None) -> dict:
        n = self._ir_n; self._ir_n += 1
        eq_id = equipment_id or _pick(_REF.get("equipment_ids", ["P-101"]))
        ir_type = _pick(self.INCIDENT_REPORT_TYPES)
        severity = _pick(["P1", "P2", "P3", "P4", "P5"])
        reporter = _pick(_REF.get("user_ids", ["USR-001"]))
        investigator = _pick([uid for uid in _REF.get("user_ids", []) if uid != reporter] or ["USR-003"])
        status = _pick(self.INCIDENT_REPORT_STATUSES)
        return {
            "id": f"IR-GEN-{n:04d}",
            "incident_number": f"INC-{datetime.utcnow().year}-GEN-{n:04d}",
            "title": f"{ir_type.replace('_', ' ').title()} — {eq_id}",
            "type": ir_type,
            "severity": severity,
            "status": status,
            "project_id": _pick(_REF.get("project_ids", ["PRJ-DEMO-001"])),
            "plant_id": _pick(_REF.get("plant_ids", ["PLT-DEMO-CDU"])),
            "equipment_ids": [eq_id],
            "location_description": f"Near {eq_id}, {_pick(self.EQUIPMENT_LOCATIONS)}",
            "incident_date": _date(-random.randint(0, 90)),
            "incident_time": f"{random.randint(6, 22):02d}:{random.choice(['00', '15', '30', '45'])}",
            "reported_by_id": reporter,
            "reported_by_name": _REF.get("user_names", {}).get(reporter, ""),
            "reported_at": _now(-random.randint(1, 90)),
            "description": _fake_sentence(20) if _fake else f"Incident occurred on {eq_id}.",
            "immediate_actions": _pick(self.CORRECTIVE_ACTIONS),
            "injured_persons": [],
            "witnesses": [],
            "investigation_team_ids": [investigator],
            "root_causes": [_pick(self.INCIDENT_CATEGORIES)] if status in ("root_cause_analysis", "capa", "closed") else [],
            "contributing_factors": [],
            "capa_items": [
                {"id": f"CAPA-{random.randint(1,9):03d}", "type": "corrective", "description": _pick(self.CORRECTIVE_ACTIONS), "assigned_to_id": investigator, "due_date": _date(30), "status": "open"}
            ] if status in ("capa", "closed") else [],
            "lessons_learned": _fake_sentence(15) if _fake else "Lessons updated in CMMS.",
            "regulatory_notification_required": random.choice([True, False]),
            "regulatory_body": None,
            "notification_deadline": None,
            "management_review_by_id": _pick([uid for uid, role in _REF.get("user_roles", {}).items() if role == "manager"] or ["USR-006"]),
            "management_review_comments": None,
            "management_reviewed_at": None,
            "audit_trail": [
                {"timestamp": _now(-5), "action": "reported", "user": _REF.get("user_names", {}).get(reporter, ""), "comments": ""},
            ],
            "created_by": reporter,
            "created_at": _now(-random.randint(1, 90)),
            "updated_at": _now(),
        }

    # ── Quality Inspection ────────────────────────────────────────────────────
    def quality_inspection(self) -> dict:
        n = self._qi_n; self._qi_n += 1
        insp_type = _pick(self.INSPECTION_TYPES)
        inspector = _pick([uid for uid, role in _REF.get("user_roles", {}).items() if role == "quality_inspector"] or _REF.get("user_ids", ["USR-007"]))
        reviewer = _pick([uid for uid in _REF.get("user_ids", []) if uid != inspector] or ["USR-005"])
        eq_ids = random.sample(_REF.get("equipment_ids", ["P-101"]), k=random.randint(0, 2))
        status = _pick(self.INSPECTION_STATUSES)
        checklist = [
            {"seq": i + 1, "category": _pick(["Visual", "Dimensional", "NDT", "Mechanical", "Documentation"]),
             "check_item": _fake_sentence(8) if _fake else f"Check item {i+1}",
             "criteria": _fake_sentence(6) if _fake else f"Acceptance criteria {i+1}",
             "result": _pick(["pass", "pass", "pass", "fail", None]),
             "findings": "", "evidence_ref": ""}
            for i in range(random.randint(4, 8))
        ]
        score = round(sum(1 for c in checklist if c["result"] == "pass") / len(checklist) * 100, 1)
        return {
            "id": f"QI-GEN-{n:04d}",
            "inspection_number": f"QI-{datetime.utcnow().year}-GEN-{n:04d}",
            "title": f"{insp_type.replace('_', ' ').title()} Inspection — {n:04d}",
            "inspection_type": insp_type,
            "project_id": _pick(_REF.get("project_ids", ["PRJ-DEMO-001"])),
            "plant_id": _pick(_REF.get("plant_ids", ["PLT-DEMO-CDU"])),
            "equipment_ids": eq_ids,
            "status": status,
            "priority": _pick(["low", "medium", "high", "critical"]),
            "scheduled_date": _date(random.randint(-10, 30)),
            "actual_date": _date(-random.randint(0, 10)) if status in ("completed", "failed", "closed_with_findings") else None,
            "inspector_id": inspector,
            "inspector_name": _REF.get("user_names", {}).get(inspector, ""),
            "checklist_items": checklist,
            "non_conformances": [
                {"id": f"NC-GEN-{random.randint(1000,9999)}", "description": _fake_sentence(10) if _fake else "Non-conformance found.", "severity": _pick(["minor", "major", "critical"]), "action_required": _pick(self.CORRECTIVE_ACTIONS), "due_date": _date(7), "status": "open"}
            ] if score < 80 else [],
            "observations": [],
            "overall_score": score if status in ("completed", "closed_with_findings") else None,
            "summary_notes": None,
            "reviewer_id": reviewer,
            "reviewer_name": _REF.get("user_names", {}).get(reviewer, ""),
            "reviewer_decision": status if status in ("completed", "closed_with_findings", "failed") else None,
            "reviewer_comments": None,
            "reviewed_at": _now(-1) if status in ("completed", "closed_with_findings") else None,
            "audit_trail": [{"timestamp": _now(-14), "action": "created", "user": _REF.get("user_names", {}).get(inspector, ""), "comments": ""}],
            "created_by": inspector,
            "created_at": _now(-14),
            "updated_at": _now(),
        }

    # ── Action Item (CAPA) ────────────────────────────────────────────────────
    def action_item(self) -> dict:
        n = self._ai_n; self._ai_n += 1
        assignee = _pick(_REF.get("user_ids", ["USR-001"]))
        verifier = _pick([uid for uid in _REF.get("user_ids", []) if uid != assignee] or ["USR-003"])
        creator = _pick([uid for uid in _REF.get("user_ids", []) if uid != assignee] or ["USR-003"])
        status = _pick(self.ACTION_STATUSES)
        return {
            "id": f"ACT-GEN-{n:04d}",
            "action_number": f"ACT-{datetime.utcnow().year}-GEN-{n:04d}",
            "title": _pick(self.CORRECTIVE_ACTIONS)[:80],
            "description": _pick(self.CORRECTIVE_ACTIONS),
            "source_type": _pick(["incident", "inspection", "audit", "near_miss"]),
            "source_id": _pick(_REF.get("mwo_ids", ["MWO-DEMO-P101"])),
            "source_ref": f"GEN-ACTION-{n:04d}",
            "action_type": _pick(self.ACTION_TYPES),
            "priority": _pick(self.ACTION_PRIORITIES),
            "status": status,
            "project_id": _pick(_REF.get("project_ids", ["PRJ-DEMO-001"])),
            "plant_id": _pick(_REF.get("plant_ids") + [None]),
            "assigned_to_id": assignee,
            "assigned_to_name": _REF.get("user_names", {}).get(assignee, ""),
            "due_date": _date(random.randint(-5, 60)),
            "completed_by_id": assignee if status in ("completed",) else None,
            "completed_by_name": _REF.get("user_names", {}).get(assignee, "") if status == "completed" else None,
            "completed_at": _now(-random.randint(1, 5)) if status == "completed" else None,
            "completion_evidence": "Evidence documented in CMMS." if status == "completed" else None,
            "verifier_id": verifier,
            "verifier_name": _REF.get("user_names", {}).get(verifier, ""),
            "verification_comments": None,
            "verified_at": None,
            "created_by": creator,
            "created_at": _now(-random.randint(5, 30)),
            "updated_at": _now(),
        }

    # ── Bulk generation ───────────────────────────────────────────────────────
    def bulk(self, n: int = 5) -> dict[str, list[dict]]:
        """Generate n new records for every entity type. Returns a dict of lists."""
        eq_ids = _REF.get("equipment_ids", ["P-101"])
        return {
            "equipment": [self.equipment() for _ in range(n)],
            "incidents": [self.incident(_pick(eq_ids)) for _ in range(n)],
            "maintenance_records": [self.maintenance_record(_pick(eq_ids)) for _ in range(n)],
            "documents": [self.document() for _ in range(n)],
            "compliance": [self.compliance(_pick(eq_ids)) for _ in range(n)],
            "spare_parts": [self.spare_part() for _ in range(n)],
            "user_profiles": [self.user_profile() for _ in range(n)],
            "projects": [self.project() for _ in range(n)],
            "plants": [self.plant() for _ in range(n)],
            "permits_to_work": [self.permit_to_work() for _ in range(n)],
            "safety_procedures": [self.safety_procedure() for _ in range(n)],
            "managed_work_orders": [self.managed_work_order(_pick(eq_ids)) for _ in range(n)],
            "incident_reports": [self.incident_report(_pick(eq_ids)) for _ in range(n)],
            "quality_inspections": [self.quality_inspection() for _ in range(n)],
            "action_items": [self.action_item() for _ in range(n)],
        }


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _serialize(obj: Any) -> Any:
    """Convert datetime/date objects to ISO strings for JSON/repr output."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    return obj


def write_model_file(
    snapshot: dict[str, list[dict]],
    generated: dict[str, list[dict]] | None,
    out_path: Path,
    include_snapshot: bool = True,
) -> None:
    """Write a ready-to-import Python module with snapshot + generated data."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '"""',
        "Auto-generated OpsBrain test data model.",
        f"Generated: {datetime.utcnow().isoformat(timespec='seconds')} UTC",
        "",
        "Contains two top-level dicts:",
        "  DB_SNAPSHOT  — exact current state of every PostgreSQL table",
        "  GENERATED    — new synthetic records consistent with the live schema",
        "",
        "Usage:",
        "  from generated_model import DB_SNAPSHOT, GENERATED",
        '"""',
        "from __future__ import annotations",
        "from typing import Any",
        "",
    ]

    if include_snapshot:
        clean_snap = _serialize(snapshot)
        lines.append("# ─────────────────────────── DB SNAPSHOT ───────────────────────────────")
        lines.append(f"DB_SNAPSHOT: dict[str, list[dict[str, Any]]] = {pformat(clean_snap, width=120, sort_dicts=False)}")
        lines.append("")

    if generated:
        clean_gen = _serialize(generated)
        lines.append("# ─────────────────────────── GENERATED DATA ────────────────────────────")
        lines.append(f"GENERATED: dict[str, list[dict[str, Any]]] = {pformat(clean_gen, width=120, sort_dicts=False)}")
        lines.append("")
    else:
        lines.append("GENERATED: dict[str, list[dict[str, Any]]] = {}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[✓] Written → {out_path}  ({out_path.stat().st_size // 1024} KB)")


def print_summary(snapshot: dict[str, list[dict]]) -> None:
    print("\n=== DB SNAPSHOT SUMMARY ===")
    for tbl, rows in snapshot.items():
        print(f"  {tbl:<30} {len(rows):>4} rows")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="OpsBrain DB test data model generator")
    ap.add_argument("--dump", action="store_true", help="Print the full DB snapshot summary to stdout")
    ap.add_argument("--generate", action="store_true", help="Generate synthetic records + write output file")
    ap.add_argument("--count", type=int, default=5, help="Number of new records per entity type (default: 5)")
    ap.add_argument("--no-snapshot", action="store_true", help="Omit the DB snapshot from the output file")
    ap.add_argument("--output", default="test_data/generated_model.py", help="Output file path (default: test_data/generated_model.py)")
    args = ap.parse_args()

    if not args.dump and not args.generate:
        ap.print_help()
        sys.exit(0)

    print("[…] Connecting to PostgreSQL…")
    snap = read_snapshot()
    print_summary(snap)

    if args.generate:
        print(f"[…] Generating {args.count} records per entity type…")
        factory = DataFactory(snap)
        generated = factory.bulk(n=args.count)
        total = sum(len(v) for v in generated.items())

        gen_summary = {k: len(v) for k, v in generated.items()}
        print("[✓] Generated records:")
        for entity, count in gen_summary.items():
            print(f"  {entity:<30} {count:>4} new records")

        out_path = Path(args.output)
        write_model_file(
            snapshot=snap,
            generated=generated,
            out_path=out_path,
            include_snapshot=not args.no_snapshot,
        )

        print(f"\n[✓] Done. Import with:")
        print(f"    from {out_path.stem} import DB_SNAPSHOT, GENERATED")


if __name__ == "__main__":
    main()
