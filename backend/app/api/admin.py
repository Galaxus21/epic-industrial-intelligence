"""
AI Operations Brain — Admin / Data Management API
Bulk-purge for every purgeable entity type, including equipment and sensors.

DELETE /api/v1/admin/purge?entity=<key>   — purge one entity type
DELETE /api/v1/admin/purge?entity=all     — full database reset
GET    /api/v1/admin/stats                — record counts per entity
POST   /api/v1/admin/generate-demo        — demo dataset covering every kept entity type

Entity keys
───────────
Assets            : equipment, maintenance, sensors, spare_parts, technicians
Operations        : incidents, saved_checklists, saved_work_orders
System            : documents, graph, compliance
                    (audit_logs is append-only and can never be purged)
"""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.auth import require_roles
from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services.audit import record as audit_record

logger = logging.getLogger(__name__)
router = APIRouter()

# Each key maps to one or more ORM model classes.
_ENTITY_MAP: dict[str, list] = {
    # ── Assets ───────────────────────────────────────────────────────────────
    "equipment":         [m.Equipment],
    "maintenance":       [m.MaintenanceRecord],
    "sensors":           [m.SensorHistory],
    "spare_parts":       [m.SparePart],
    "technicians":       [m.Technician],
    # ── Operations ───────────────────────────────────────────────────────────
    "incidents":         [m.Incident],
    "saved_checklists":  [m.SavedChecklist],
    "saved_work_orders": [m.SavedWorkOrder],
    # ── System ───────────────────────────────────────────────────────────────
    "documents":         [m.DocumentRecord],
    # NOTE: audit_logs is intentionally NOT purgeable — the audit trail is
    # append-only evidence and must survive administrative resets.
    "graph":             [m.GraphNode, m.GraphLink],
    "compliance":        [m.Compliance],
}


async def _purge_one(entity: str, db) -> tuple[int, list[str]]:
    """Delete all DB rows for the given entity key.
    Returns (count_deleted, files_to_remove_after_commit).
    Files are NOT removed here — caller must remove them after a successful commit.
    """
    models = _ENTITY_MAP.get(entity, [])
    total = 0
    pending_files: list[str] = []

    for model in models:
        n = await db.scalar(select(func.count()).select_from(model)) or 0
        await db.execute(delete(model))
        total += n

    # Collect file paths to delete AFTER the DB commit succeeds
    if entity == "documents":
        if os.path.isdir("uploads"):
            for fname in os.listdir("uploads"):
                fpath = os.path.join("uploads", fname)
                if os.path.isfile(fpath):
                    pending_files.append(fpath)

    return total, pending_files


# ─── Purge endpoint ───────────────────────────────────────────────────────────

@router.delete("/purge")
async def purge_entity(
    entity: str = Query(..., description="Entity key to purge, or 'all' for full reset"),
    user: m.UserProfile = Depends(require_roles("manager")),
):
    """Delete ALL records for the given entity type, or 'all' for everything.

    Manager-only. Audit logs are never purgeable, and the purge itself is
    written to the audit trail before any rows are deleted.
    """
    if entity == "audit_logs":
        raise HTTPException(403, "Audit logs are append-only and cannot be purged")
    if entity == "all":
        keys = list(_ENTITY_MAP.keys())
    elif entity not in _ENTITY_MAP:
        raise HTTPException(
            400,
            f"Unknown entity '{entity}'. Valid keys: {list(_ENTITY_MAP)} or 'all'",
        )
    else:
        keys = [entity]

    # Record intent before deleting so the purge cannot erase its own evidence
    await audit_record("purge", "system", entity, actor=user.name, actor_type="user",
                       notes=f"Admin purge requested for entity '{entity}'")

    total = 0
    all_pending_files: list[str] = []
    async with AsyncSessionLocal() as db:
        for key in keys:
            count, pending = await _purge_one(key, db)
            total += count
            all_pending_files.extend(pending)
        # Commit DB changes first — only remove files if commit succeeds
        await db.commit()

    # Remove files AFTER successful DB commit (prevents orphaned files on rollback)
    for fpath in all_pending_files:
        try:
            os.remove(fpath)
        except OSError:
            pass

    logger.info("Admin purge: entity=%s deleted=%d rows", entity, total)
    return {"entity": entity, "deleted": total, "status": "ok"}


# ─── Stats endpoint ───────────────────────────────────────────────────────────

@router.get("/stats")
async def get_entity_stats():
    """Return record counts for every entity type."""
    async with AsyncSessionLocal() as db:
        counts: dict[str, int] = {}
        for key, models in _ENTITY_MAP.items():
            n = 0
            for model in models:
                n += await db.scalar(select(func.count()).select_from(model)) or 0
            counts[key] = n
    return counts


# ─── Demo doc download endpoint ──────────────────────────────────────────────

@router.get("/demo-docs/{filename}")
async def download_demo_doc(filename: str):
    """Download a generated sample document for manual upload."""
    from fastapi.responses import FileResponse
    from app.services.demo_docs import UPLOADS_DIR
    safe_name = os.path.basename(filename)
    fpath = os.path.join(UPLOADS_DIR, safe_name)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail=f"Demo doc '{safe_name}' not found. Run generate-demo first.")
    return FileResponse(fpath, filename=safe_name, media_type="application/octet-stream")


# ─── Full demo dataset generator ─────────────────────────────────────────────

@router.post("/generate-demo")
async def generate_full_demo(user: m.UserProfile = Depends(require_roles("manager"))):
    """
    Generate a rich demo dataset covering every kept entity type.
    Safe to call multiple times — uses fixed IDs so every row is idempotent.
    """
    from datetime import datetime, timedelta
    from app.services import db_service as db
    from app.services import vector_service as vs

    created: dict[str, int] = {}

    def _d(days_ago: int) -> str:
        return (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

    # 1. USERS
    users_data = [
        {"id": "USR-DEMO-001", "employee_id": "EMP-001", "name": "Rajesh Kumar",
         "email": "rajesh.kumar@apexrefinery.in", "department": "Maintenance",
         "role": "technician", "certifications": ["HAZOP"]},
        {"id": "USR-DEMO-005", "employee_id": "EMP-005", "name": "Ahmed Khan",
         "email": "ahmed.khan@apexrefinery.in", "department": "Maintenance",
         "role": "supervisor", "certifications": []},
        {"id": "USR-DEMO-006", "employee_id": "EMP-006", "name": "Deepa Menon",
         "email": "deepa.menon@apexrefinery.in", "department": "Management",
         "role": "manager", "certifications": ["PMP", "Six Sigma Black Belt"]},
    ]
    async with AsyncSessionLocal() as s:
        for u in users_data:
            stmt = pg_insert(m.UserProfile).values(**u).on_conflict_do_nothing()
            await s.execute(stmt)
        await s.commit()
    created["users"] = len(users_data)

    # 2. EQUIPMENT
    equipment_data = [
        {"id": "P-101", "name": "Crude Oil Feed Pump", "type": "Centrifugal Pump",
         "location": "Unit 4 — CDU", "health_score": 72.0, "failure_probability": 31.0,
         "compliance_score": 78.0, "maintenance_due_days": -3, "criticality": "Critical",
         "status": "Running — Alert", "manufacturer": "Flowserve", "model": "PVXM-100",
         "installed_date": "2018-04-15",
         "current_readings": {
             "vibration_de": {"value": 7.4, "unit": "mm/s", "normal": 4.5, "alarm": 7.1, "trip": 11.2},
             "bearing_temp_de": {"value": 78, "unit": "°C", "normal": 55, "alarm": 75},
             "discharge_pressure": {"value": 8.2, "unit": "bar", "normal": 8.5, "alarm": 6.0},
             "flow_rate": {"value": 242, "unit": "m³/hr", "normal": 250, "alarm": 200},
         },
         "downstream_equipment": ["HX-201"], "technicians": ["Rajesh Kumar", "Amit Shah"],
         "specifications": {"rated_flow": "250 m³/hr", "rated_head": "70 m", "motor_power": "55 kW"}},
        {"id": "P-202", "name": "Reflux Pump", "type": "Centrifugal Pump",
         "location": "Unit 4 — CDU", "health_score": 85.0, "failure_probability": 8.0,
         "compliance_score": 92.0, "maintenance_due_days": 22, "criticality": "High",
         "status": "Running", "manufacturer": "Sulzer", "model": "MBN50-160",
         "installed_date": "2020-07-10",
         "current_readings": {
             "vibration_de": {"value": 3.1, "unit": "mm/s", "normal": 4.5, "alarm": 7.1},
             "bearing_temp_de": {"value": 51, "unit": "°C", "normal": 55, "alarm": 75},
         },
         "downstream_equipment": [], "technicians": ["Rajesh Kumar"],
         "specifications": {"rated_flow": "180 m³/hr", "rated_head": "50 m", "motor_power": "37 kW"}},
        {"id": "HX-201", "name": "Crude Feed Pre-heater", "type": "Heat Exchanger",
         "location": "Unit 4 — CDU", "health_score": 88.0, "failure_probability": 7.0,
         "compliance_score": 95.0, "maintenance_due_days": 45, "criticality": "High",
         "status": "Running", "manufacturer": "GEA", "model": "HX-ST-450",
         "installed_date": "2017-09-01",
         "current_readings": {
             "tube_side_dp": {"value": 1.8, "unit": "bar", "normal": 2.0, "alarm": 3.5},
             "shell_side_temp_out": {"value": 142, "unit": "°C", "normal": 145, "alarm": 160},
         },
         "upstream_equipment": ["P-101"], "downstream_equipment": ["V-301"],
         "specifications": {"duty": "12.5 MW", "area": "450 m²"}},
        {"id": "V-301", "name": "Crude Feed Surge Drum", "type": "Pressure Vessel",
         "location": "Unit 4 — CDU", "health_score": 95.0, "failure_probability": 2.0,
         "compliance_score": 100.0, "maintenance_due_days": 90, "criticality": "Critical",
         "status": "Running", "manufacturer": "L&T Heavy Engineering", "model": "V-H-3200",
         "installed_date": "2016-11-20",
         "current_readings": {
             "level": {"value": 65, "unit": "%", "normal": 60, "alarm": 85, "trip": 90},
             "pressure": {"value": 3.2, "unit": "barg", "normal": 3.5, "alarm": 5.0, "trip": 6.0},
         },
         "upstream_equipment": ["HX-201"],
         "specifications": {"volume": "120 m³", "design_pressure": "6 barg", "design_temp": "200°C"}},
        {"id": "K-401", "name": "Process Air Compressor", "type": "Compressor",
         "location": "Unit 5 — VDU", "health_score": 65.0, "failure_probability": 25.0,
         "compliance_score": 78.0, "maintenance_due_days": 3, "criticality": "High",
         "status": "Running — Alert", "manufacturer": "Atlas Copco", "model": "ZH350",
         "installed_date": "2019-03-15",
         "current_readings": {
             "discharge_pressure": {"value": 10.8, "unit": "bar", "normal": 12.5, "alarm": 9.0},
             "vibration": {"value": 4.2, "unit": "mm/s", "normal": 3.5, "alarm": 5.5},
             "discharge_temp": {"value": 185, "unit": "°C", "normal": 175, "alarm": 200},
         },
         "specifications": {"capacity": "35 000 Nm³/hr", "discharge_pressure": "12.5 bar"}},
        {"id": "G-101", "name": "Cooling Tower Fan", "type": "Fan",
         "location": "Unit 5 — VDU", "health_score": 78.0, "failure_probability": 12.0,
         "compliance_score": 88.0, "maintenance_due_days": 14, "criticality": "Medium",
         "status": "Running", "manufacturer": "Howden", "model": "AF-1800",
         "installed_date": "2021-05-10",
         "current_readings": {
             "vibration": {"value": 2.8, "unit": "mm/s", "normal": 3.0, "alarm": 5.0},
             "current": {"value": 145, "unit": "A", "normal": 150, "alarm": 175},
         },
         "specifications": {"airflow": "850 000 m³/hr", "motor_power": "110 kW"}},
    ]
    for eq in equipment_data:
        await db.upsert_equipment(eq)
        await db.upsert_graph_node({"id": eq["id"], "name": f"{eq['id']}\n{eq['type'][:14]}", "type": "equipment", "val": 18})
    created["equipment"] = len(equipment_data)

    # 3. COMPLIANCE
    compliance_data = [
        {"equipment_id": "P-101", "overall_score": 78, "status": "Warning",
         "issues": [
             {"id": "CI-P101-1", "item": "OISD-117 Sec 8.3: Alarm response time exceeded — 4hrs without shutdown", "severity": "High", "standard": "OISD-117"},
             {"id": "CI-P101-2", "item": "ISO 10816-7: Vibration in Zone C — immediate action required", "severity": "High", "standard": "ISO 10816-7"},
             {"id": "CI-P101-3", "item": "Lubrication interval 42d — SOP-P101-BEARING requires ≤30d", "severity": "Medium", "standard": "SOP-P101-BEARING"},
         ],
         "passed": [
             {"item": "OISD-117 Sec 4.1: Work-permit procedure in place"},
             {"item": "Factory Act 1948: Maintenance records current"},
             {"item": "API 610: Mechanical seal within service interval"},
         ]},
        {"equipment_id": "P-202", "overall_score": 92, "status": "Compliant",
         "issues": [{"id": "CI-P202-1", "item": "Minor: Anti-vibration mount inspection overdue 5 days", "severity": "Low", "standard": "OEM Manual"}],
         "passed": [{"item": "OISD-117: All alarms functional"}, {"item": "Seal integrity: Pass"}]},
        {"equipment_id": "HX-201", "overall_score": 95, "status": "Compliant",
         "issues": [], "passed": [{"item": "API 660: Tube inspection current"}, {"item": "Pressure test: Current"}]},
        {"equipment_id": "V-301", "overall_score": 100, "status": "Compliant",
         "issues": [], "passed": [{"item": "IBR: Stamp current 2027"}, {"item": "Safety valve tested 2026-01"}, {"item": "Thickness survey 2025: Pass"}]},
        {"equipment_id": "K-401", "overall_score": 78, "status": "Warning",
         "issues": [
             {"id": "CI-K401-1", "item": "Discharge pressure 10.8 bar — rated 12.5 bar, performance degraded 14%", "severity": "High", "standard": "ASME B19.3"},
             {"id": "CI-K401-2", "item": "Vibration trending up — 4.2 mm/s (alarm 5.5)", "severity": "Medium", "standard": "ISO 10816"},
         ],
         "passed": [{"item": "Motor insulation resistance: Pass"}, {"item": "Pressure relief valve: Current"}]},
        {"equipment_id": "G-101", "overall_score": 88, "status": "Compliant",
         "issues": [{"id": "CI-G101-1", "item": "Fan blade erosion coating inspection due", "severity": "Low", "standard": "OEM Howden AF"}],
         "passed": [{"item": "Motor thermal protection: Functional"}, {"item": "Vibration: Normal"}]},
    ]
    for c in compliance_data:
        await db.upsert_compliance(c)
    created["compliance"] = len(compliance_data)

    # 4. SPARE PARTS
    spare_parts_data = [
        {"id": "SP-DEMO-001", "name": "SKF Bearing 6311 (Deep Groove)", "part_number": "SKF-6311-2RS",
         "equipment_ids": ["P-101", "P-202"], "quantity_on_hand": 3, "reorder_point": 2,
         "lead_time_days": 7, "location": "Warehouse A — Rack 4", "unit_cost_usd": 280, "status": "Available"},
        {"id": "SP-DEMO-002", "name": "John Crane Mechanical Seal 8B-1 Type-2", "part_number": "JC-8B1-T2",
         "equipment_ids": ["P-101", "P-202"], "quantity_on_hand": 1, "reorder_point": 2,
         "lead_time_days": 14, "location": "Warehouse A — Rack 5", "unit_cost_usd": 3200, "status": "Low Stock"},
        {"id": "SP-DEMO-003", "name": "HX-201 Tube Bundle Gasket Set", "part_number": "GEA-HX450-GS",
         "equipment_ids": ["HX-201"], "quantity_on_hand": 2, "reorder_point": 1,
         "lead_time_days": 21, "location": "Warehouse B — Row 2", "unit_cost_usd": 1850, "status": "Available"},
        {"id": "SP-DEMO-004", "name": "K-401 Inlet Filter Element", "part_number": "AC-ZH350-FE",
         "equipment_ids": ["K-401"], "quantity_on_hand": 4, "reorder_point": 3,
         "lead_time_days": 5, "location": "Warehouse B — Row 6", "unit_cost_usd": 450, "status": "Available"},
    ]
    async with AsyncSessionLocal() as s:
        for sp in spare_parts_data:
            if not await s.get(m.SparePart, sp["id"]):
                s.add(m.SparePart(**sp))
        await s.commit()
    created["spare_parts"] = len(spare_parts_data)

    # 5. INCIDENTS
    incidents_data = [
        {"id": "INC-2022-034", "equipment_id": "P-101", "date": "2022-08-14",
         "title": "Drive-end bearing failure after vibration alarm",
         "severity": "High", "root_cause_category": "Maintenance",
         "symptom": "Vibration increased from 4.2 to 8.7 mm/s over 6 hours. High-pitched noise from DE bearing.",
         "root_cause": "Bearing wear due to lubrication interval exceeded by 15 days.",
         "action_taken": "Emergency shutdown at 9.1 mm/s. Replaced SKF 6311 bearing. Updated lube SOP to 14-day interval.",
         "lessons_learned": "Vibration alarms >7.1 mm/s for >2hrs indicate imminent bearing failure within 18hrs.",
         "downtime_hours": 12, "cost_usd": 14200, "technician": "Rajesh Kumar",
         "keywords": ["vibration", "bearing", "lubrication", "wear", "centrifugal pump"]},
        {"id": "INC-2021-011", "equipment_id": "P-101", "date": "2021-03-22",
         "title": "Mechanical seal leakage — routine inspection",
         "severity": "Medium", "root_cause_category": "Wear",
         "symptom": "Seal flush leakage detected at Plan 11 piping. API seal chamber pressure dropped 0.3 bar.",
         "root_cause": "Mechanical seal O-ring hardening after 30 months in service. Normal wear.",
         "action_taken": "Replaced complete mechanical seal assembly with upgraded Type-2 seal.",
         "lessons_learned": "Schedule seal inspection at 36-month mark. Type-2 seal more durable.",
         "downtime_hours": 8, "cost_usd": 8500, "technician": "Amit Shah",
         "keywords": ["seal", "leakage", "mechanical seal", "O-ring", "plan 11"]},
        {"id": "INC-2023-067", "equipment_id": "P-202", "date": "2023-11-08",
         "title": "Vibration spike — P-202 (similar to P-101 2022 pattern)",
         "severity": "High", "root_cause_category": "Process",
         "symptom": "Vibration increased to 7.8 mm/s. DE bearing failure 14 hours later.",
         "root_cause": "Cavitation due to inadequate NPSH margin during high-throughput operation.",
         "action_taken": "Installed inlet strainer, adjusted operating point to 85% BEP.",
         "lessons_learned": "Similar vibration signature to P-101 INC-2022-034 but different root cause.",
         "downtime_hours": 36, "cost_usd": 31000, "technician": "Priya Nair",
         "keywords": ["vibration", "bearing", "cavitation", "NPSH", "P-202"]},
        {"id": "INC-2024-015", "equipment_id": "K-401", "date": "2024-03-05",
         "title": "K-401 discharge pressure drop — filter choking",
         "severity": "Medium", "root_cause_category": "Maintenance",
         "symptom": "Discharge pressure dropped from 12.5 to 10.2 bar over 48 hrs.",
         "root_cause": "Inlet filter element completely choked with particulate. Replacement overdue by 3 weeks.",
         "action_taken": "Replaced filter element AC-ZH350-FE. Pressure restored to 12.4 bar.",
         "lessons_learned": "Filter replacement interval reduced from 90 to 60 days for this compressor.",
         "downtime_hours": 4, "cost_usd": 2200, "technician": "Ahmed Khan",
         "keywords": ["compressor", "pressure drop", "filter", "K-401"]},
    ]
    for inc in incidents_data:
        await db.upsert_incident(inc)
        await db.upsert_graph_node({"id": inc["id"], "name": f"Incident\n{inc['equipment_id']}\n{inc['severity']}", "type": "incident", "val": 14})
        await db.add_graph_link(inc["equipment_id"], inc["id"], "HAS_INCIDENT")
        await vs.index_incident(
            incident_id=inc["id"], title=inc["title"], description=inc["symptom"],
            equipment_id=inc["equipment_id"], severity=inc["severity"], date=inc["date"]
        )
    await db.add_graph_link("INC-2022-034", "INC-2023-067", "SIMILAR_PATTERN")
    created["incidents"] = len(incidents_data)

    # 6. MAINTENANCE RECORDS
    maint_records = [
        {"id": "MR-P101-VIB-01", "equipment_id": "P-101", "date": _d(45), "type": "Preventive",
         "description": "Routine vibration check and lubrication. DE bearing greased with 2 cartridges LGMT-2.",
         "status": "Completed", "findings": "Vibration 4.2 mm/s — within normal range. Bearing housing clean.",
         "technician": "Rajesh Kumar"},
        {"id": "MR-P101-VIB-02", "equipment_id": "P-101", "date": _d(15), "type": "Corrective",
         "description": "Unscheduled check following vibration trend increase.",
         "status": "Completed", "findings": "Vibration 6.1 mm/s — elevated, trending up. Lubrication applied.",
         "technician": "Rajesh Kumar"},
        {"id": "MR-P202-SEAL-01", "equipment_id": "P-202", "date": _d(60), "type": "Preventive",
         "description": "Annual mechanical seal inspection per SOP-P202-SEAL.",
         "status": "Completed", "findings": "Seal flush normal. O-ring condition acceptable. Service life 28/36 months.",
         "technician": "Amit Shah"},
        {"id": "MR-K401-FILTER-01", "equipment_id": "K-401", "date": _d(5), "type": "Corrective",
         "description": "Emergency filter replacement following pressure drop event.",
         "status": "Completed", "findings": "Old filter 98% blocked with iron oxide particles. New element installed.",
         "technician": "Ahmed Khan"},
        {"id": "MR-HX201-INSP-01", "equipment_id": "HX-201", "date": _d(90), "type": "Inspection",
         "description": "Annual tube bundle inspection and cleaning per API 660.",
         "status": "Completed", "findings": "2 of 450 tubes plugged. Fouling factor within design limit. Cleaned shell side.",
         "technician": "Dr. Anand Sharma"},
    ]
    for mr in maint_records:
        await db.upsert_maintenance_record(mr)
    created["maintenance_records"] = len(maint_records)

    # 7. SENSOR HISTORY (30-day trending)
    import random
    random.seed(42)

    p101_vib_readings = []
    for day in range(30, 0, -1):
        ts = (datetime.utcnow() - timedelta(days=day)).isoformat()
        base = 4.0 + (30 - day) * (3.4 / 30)
        noise = random.uniform(-0.15, 0.15)
        p101_vib_readings.append({"ts": ts, "value": round(base + noise, 2), "unit": "mm/s"})
    await db.upsert_sensor_history("P-101", "vibration_de", p101_vib_readings)

    k401_pres_readings = []
    for day in range(30, 0, -1):
        ts = (datetime.utcnow() - timedelta(days=day)).isoformat()
        base = 12.4 - (30 - day) * (1.6 / 30)
        noise = random.uniform(-0.08, 0.08)
        k401_pres_readings.append({"ts": ts, "value": round(base + noise, 2), "unit": "bar"})
    await db.upsert_sensor_history("K-401", "discharge_pressure", k401_pres_readings)
    created["sensor_history"] = "P-101 vibration + K-401 pressure (30d)"

    # 8. KNOWLEDGE GRAPH
    await db.add_graph_link("P-101", "HX-201", "FEEDS")
    await db.add_graph_link("HX-201", "V-301", "FEEDS")
    created["graph_nodes+links"] = "equipment+incidents"

    # 9. DEMO DOCUMENTS
    from app.services.demo_docs import generate_demo_documents
    doc_records = generate_demo_documents()
    demo_doc_files = [
        {"doc_id": d["id"], "filename": d["name"]}
        for d in doc_records
    ]

    total = sum(v if isinstance(v, int) else 0 for v in created.values())
    return {
        "status": "ok",
        "created": created,
        "total_entities": total,
        "demo_query": "Navigate to /query → select P-101 → ask: 'Pump vibration increased today. Can I continue operating?'",
        "demo_doc_files": demo_doc_files,
        "highlights": [
            "P-101: vibration at 7.4 mm/s (alarm 7.1) — TRENDING UP 30 days",
            "K-401: discharge pressure declining 10.8/12.5 bar — filter choked",
            "4 historical incidents with similarity patterns for AI learning",
        ],
    }
