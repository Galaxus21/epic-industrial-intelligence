"""
AI Operations Brain — Admin / Data Management API
Bulk-purge for every entity type, including projects, plants, equipment, sensors.

DELETE /api/v1/admin/purge?entity=<key>   — purge one entity type
DELETE /api/v1/admin/purge?entity=all     — full database reset
GET    /api/v1/admin/stats                — record counts per entity
POST   /api/v1/admin/seed-demo            — minimal single-scenario seed
POST   /api/v1/admin/generate-demo        — full rich dataset (60+ entities)

Entity keys
───────────
Project hierarchy : projects, plants
Assets            : equipment, maintenance, sensors, spare_parts, technicians
Operations        : drawings, procedures, permits, work_orders, incidents,
                    inspections, action_items, saved_checklists, saved_work_orders
System            : documents, dashboards, audit_logs, graph, compliance
"""
import logging
import os

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import delete, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services.drawing_service import ENG_DRAWINGS_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

# Each key maps to one or more ORM model classes.
_ENTITY_MAP: dict[str, list] = {
    # ── Project hierarchy ────────────────────────────────────────────────────
    "projects":          [m.Project],
    "plants":            [m.Plant],
    # ── Assets ───────────────────────────────────────────────────────────────
    "equipment":         [m.Equipment],
    "maintenance":       [m.MaintenanceRecord],
    "sensors":           [m.SensorHistory],
    "spare_parts":       [m.SparePart],
    "technicians":       [m.Technician],
    # ── Operations ───────────────────────────────────────────────────────────
    "drawings":          [m.Drawing],
    "procedures":        [m.SafetyProcedure],
    "permits":           [m.PermitToWork],
    "work_orders":       [m.ManagedWorkOrder],
    "incidents":         [m.IncidentReport],
    "inspections":       [m.QualityInspection],
    "action_items":      [m.ActionItem],
    "saved_checklists":  [m.SavedChecklist],
    "saved_work_orders": [m.SavedWorkOrder],
    # ── System ───────────────────────────────────────────────────────────────
    "documents":         [m.DocumentRecord],
    "dashboards":        [m.CustomDashboard],
    "audit_logs":        [m.AuditLog],
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
    if entity == "drawings" and os.path.isdir(ENG_DRAWINGS_DIR):
        pending_files = [
            os.path.join(ENG_DRAWINGS_DIR, f)
            for f in os.listdir(ENG_DRAWINGS_DIR)
        ]

    if entity == "documents":
        for sub in ["uploads", "uploads/drawings"]:
            if os.path.isdir(sub):
                for fname in os.listdir(sub):
                    fpath = os.path.join(sub, fname)
                    if os.path.isfile(fpath):
                        pending_files.append(fpath)

    return total, pending_files


# ─── Purge endpoint ───────────────────────────────────────────────────────────

@router.delete("/purge")
async def purge_entity(
    entity: str = Query(..., description="Entity key to purge, or 'all' for full reset"),
):
    """Delete ALL records for the given entity type, or 'all' for everything."""
    if entity == "all":
        keys = list(_ENTITY_MAP.keys())
    elif entity not in _ENTITY_MAP:
        raise HTTPException(
            400,
            f"Unknown entity '{entity}'. Valid keys: {list(_ENTITY_MAP)} or 'all'",
        )
    else:
        keys = [entity]

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


# ─── Demo doc download endpoints ─────────────────────────────────────────────

@router.get("/demo-docs")
async def list_demo_docs():
    """List sample documents available for manual upload via the Documents page."""
    from app.services.demo_docs import UPLOADS_DIR, generate_demo_documents
    import os
    # Generate if not already on disk
    demo_dir = UPLOADS_DIR
    if not os.path.isdir(demo_dir) or not os.listdir(demo_dir):
        generate_demo_documents()
    files = []
    for fname in sorted(os.listdir(demo_dir)):
        fpath = os.path.join(demo_dir, fname)
        if os.path.isfile(fpath):
            files.append({
                "filename": fname,
                "size_bytes": os.path.getsize(fpath),
                "download_url": f"/api/v1/admin/demo-docs/{fname}",
            })
    return {"files": files}


@router.get("/demo-docs/{filename}")
async def download_demo_doc(filename: str):
    """Download a generated sample document for manual upload."""
    from fastapi.responses import FileResponse
    from app.services.demo_docs import UPLOADS_DIR
    import os
    # Sanitise — no path traversal
    safe_name = os.path.basename(filename)
    fpath = os.path.join(UPLOADS_DIR, safe_name)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail=f"Demo doc '{safe_name}' not found. Run generate-demo first.")
    return FileResponse(fpath, filename=safe_name, media_type="application/octet-stream")


# ─── Demo scenario seed ───────────────────────────────────────────────────────

@router.post("/seed-demo")
async def seed_demo_scenario():
    """
    Inject one complete demo scenario into the live DB without restarting.
    Creates: equipment with active alarm · incident report · managed work order
             · compliance issue · PTW · quality inspection.

    Safe to call multiple times — uses fixed IDs so rows are idempotent.
    """
    import uuid
    from datetime import datetime, date
    from app.services import db_service as db
    from app.services import vector_service as vs

    today = date.today().isoformat()
    now   = datetime.utcnow().isoformat()

    # ── Equipment — P-101 Crude Oil Feed Pump with vibration alarm ────────────
    eq_id = "P-101-DEMO"
    await db.upsert_equipment({
        "id":   eq_id,
        "name": "Crude Oil Feed Pump (Demo)",
        "type": "Centrifugal Pump",
        "location":            "Unit 4 — CDU",
        "health_score":        72.0,
        "failure_probability": 31.0,
        "compliance_score":    78.0,
        "maintenance_due_days": -3,          # overdue
        "criticality": "Critical",
        "status":      "Running — Alert",
        "manufacturer": "Flowserve",
        "model":        "PVXM-100",
        "current_readings": {
            "vibration_de":  {"value": 7.4, "unit": "mm/s", "normal": 4.5, "alarm": 7.1, "trip": 11.2},
            "bearing_temp":  {"value": 78,  "unit": "°C",   "normal": 55,  "alarm": 75},
            "discharge_pres":{"value": 8.2, "unit": "bar",  "normal": 8.5, "alarm": 6.0},
        },
        "technicians": ["Rajesh Kumar", "Amit Shah"],
    })
    await db.upsert_graph_node({"id": eq_id, "name": f"{eq_id}\nCrude Pump", "type": "equipment", "val": 18})

    # ── Incident Report — recent P2 bearing vibration ─────────────────────────
    ir_id = "IR-DEMO-001"
    async with AsyncSessionLocal() as s:
        existing = await s.get(m.IncidentReport, ir_id)
        if not existing:
            obj = m.IncidentReport(
                id=ir_id,
                incident_number="INC-DEMO-2026-001",
                title="Vibration spike on crude oil pump — potential bearing failure",
                description="Operator reported vibration reading increased to 7.4 mm/s, exceeding 7.1 mm/s alarm threshold on drive-end bearing. Similar pattern to INC-2022-034.",
                incident_type="near_miss",
                severity="P2",
                status="reported",
                equipment_ids=[eq_id],
                occurred_at=today,
                reported_at=now,
                reported_by_name="Rajesh Kumar",
                downtime_hours=0.0,
                root_cause_category="Mechanical",
            )
            s.add(obj)
            await s.commit()
    # Index into Qdrant for semantic search
    await vs.index_incident(
        incident_id=ir_id,
        title="Vibration spike on crude oil pump — potential bearing failure",
        description="Operator reported vibration reading increased to 7.4 mm/s, exceeding 7.1 mm/s alarm threshold on drive-end bearing. Similar pattern to INC-2022-034.",
        equipment_id=eq_id, severity="P2", date=today,
    )
    await db.upsert_graph_node({"id": ir_id, "name": "Incident\nVibration\nP2", "type": "incident", "val": 14})
    await db.add_graph_link(eq_id, ir_id, "HAS_INCIDENT")

    # ── Managed Work Order — corrective maintenance ───────────────────────────
    wo_id = "MWO-DEMO-001"
    async with AsyncSessionLocal() as s:
        existing = await s.get(m.ManagedWorkOrder, wo_id)
        if not existing:
            obj = m.ManagedWorkOrder(
                id=wo_id,
                wo_number="WO-DEMO-2026-001",
                title="Inspect and replace DE bearing on crude oil pump",
                description="Corrective maintenance triggered by vibration alarm. Inspect drive-end bearing, replace SKF 6311 if worn, check lubrication interval compliance.",
                category="corrective",
                priority="high",
                status="approved",
                equipment_ids=[eq_id],
                estimated_hours=4.0,
                created_by_name="System (Demo)",
            )
            s.add(obj)
            await s.commit()
    await db.upsert_graph_node({"id": wo_id, "name": "WO\nBearing\nHigh", "type": "work_order", "val": 14})
    await db.add_graph_link(eq_id, wo_id, "HAS_WORK_ORDER")

    # ── Compliance — record with open issues ──────────────────────────────────
    await db.upsert_compliance({
        "equipment_id":  eq_id,
        "overall_score": 78,
        "status":        "Warning",
        "issues": [
            {"id": "CI-01", "item": "OISD-117 Sec 8.3: Alarm response time exceeded", "severity": "High"},
            {"id": "CI-02", "item": "ISO 10816-7: Vibration level in Zone C — immediate action required", "severity": "High"},
            {"id": "CI-03", "item": "Lubrication interval 42 days — SOP requires 30 days max", "severity": "Medium"},
        ],
        "passed": [
            {"item": "OISD-117 Sec 4.1: PTW procedure in place"},
            {"item": "Factory Act 1948: Maintenance records current"},
        ],
    })

    # ── PTW — draft permit for bearing replacement ────────────────────────────
    ptw_id = "PTW-DEMO-001"
    async with AsyncSessionLocal() as s:
        existing = await s.get(m.PermitToWork, ptw_id)
        if not existing:
            obj = m.PermitToWork(
                id=ptw_id,
                permit_number="PTW-DEMO-2026-001",
                permit_type="cold_work",
                title="Bearing replacement on P-101-DEMO — Unit 4 CDU",
                scope_of_work="Remove and replace drive-end bearing on crude oil pump. Isolate pump suction/discharge, lock out/tag out, verify zero energy.",
                equipment_ids=[eq_id],
                status="submitted",
                originator_name="Rajesh Kumar",
                originator_date=today,
            )
            s.add(obj)
            await s.commit()

    # ── Quality Inspection — scheduled pre-maintenance ────────────────────────
    qi_id = "QI-DEMO-001"
    async with AsyncSessionLocal() as s:
        existing = await s.get(m.QualityInspection, qi_id)
        if not existing:
            obj = m.QualityInspection(
                id=qi_id,
                inspection_number="QI-DEMO-2026-001",
                title="Pre-maintenance equipment inspection — P-101-DEMO",
                inspection_type="equipment",
                status="scheduled",
                priority="high",
                equipment_ids=[eq_id],
                scheduled_date=today,
                summary_notes="Inspect bearing condition, check shaft runout, verify seal integrity before WO execution.",
            )
            s.add(obj)
            await s.commit()

    return {
        "status": "ok",
        "created": {
            "equipment": eq_id,
            "incident_report": ir_id,
            "work_order": wo_id,
            "ptw": ptw_id,
            "inspection": qi_id,
            "compliance_score": 78,
        },
        "message": (
            f"Demo scenario loaded. Navigate to /query, select equipment '{eq_id}', "
            "then ask: 'Pump vibration increased today. Can I continue operating?'"
        ),
    }


# ─── Full demo dataset generator ─────────────────────────────────────────────

@router.post("/generate-demo")
async def generate_full_demo():
    """
    Generate a rich, complete demo dataset across ALL entity types.
    Safe to call multiple times — uses fixed IDs so every row is idempotent.

    Creates:
      1 project · 2 plants · 6 equipment · 6 compliance records
      6 users · 3 spare parts
      4 legacy incidents · 3 incident reports · 5 maintenance records
      4 managed work orders · 3 PTWs · 3 safety procedures
      3 quality inspections · 3 action items · 30-day sensor history
      Knowledge-graph nodes + links for all entities
    """
    from datetime import datetime, date, timedelta
    from app.services import db_service as db
    from app.services import vector_service as vs

    TODAY = date.today().isoformat()
    NOW   = datetime.utcnow().isoformat()
    created: dict[str, int] = {}

    def _d(days_ago: int) -> str:
        return (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

    # ═══════════════════════════════════════════════════════════
    # 1. USERS (6 roles)
    # ═══════════════════════════════════════════════════════════
    users_data = [
        {"id": "USR-DEMO-001", "employee_id": "EMP-001", "name": "Rajesh Kumar",
         "email": "rajesh.kumar@apexrefinery.in", "department": "Maintenance",
         "role": "technician", "plant_ids": ["PLT-DEMO-CDU"], "certifications": ["HAZOP", "PTW-Technician"]},
        {"id": "USR-DEMO-002", "employee_id": "EMP-002", "name": "Priya Nair",
         "email": "priya.nair@apexrefinery.in", "department": "HSE",
         "role": "safety_officer", "plant_ids": ["PLT-DEMO-CDU", "PLT-DEMO-VDU"], "certifications": ["NEBOSH", "PTW-Safety"]},
        {"id": "USR-DEMO-003", "employee_id": "EMP-003", "name": "Suresh Patel",
         "email": "suresh.patel@apexrefinery.in", "department": "Operations",
         "role": "area_authority", "plant_ids": ["PLT-DEMO-CDU"], "certifications": ["PTW-AA", "HAZOP Leader"]},
        {"id": "USR-DEMO-004", "employee_id": "EMP-004", "name": "Dr. Anand Sharma",
         "email": "anand.sharma@apexrefinery.in", "department": "QA",
         "role": "quality_inspector", "plant_ids": ["PLT-DEMO-CDU", "PLT-DEMO-VDU"], "certifications": ["Lead Auditor ISO 9001", "API 510"]},
        {"id": "USR-DEMO-005", "employee_id": "EMP-005", "name": "Ahmed Khan",
         "email": "ahmed.khan@apexrefinery.in", "department": "Maintenance",
         "role": "supervisor", "plant_ids": ["PLT-DEMO-CDU"], "certifications": ["PTW-AP"]},
        {"id": "USR-DEMO-006", "employee_id": "EMP-006", "name": "Deepa Menon",
         "email": "deepa.menon@apexrefinery.in", "department": "Management",
         "role": "manager", "plant_ids": ["PLT-DEMO-CDU", "PLT-DEMO-VDU"], "certifications": ["PMP", "Six Sigma Black Belt"]},
    ]
    async with AsyncSessionLocal() as s:
        for u in users_data:
            stmt = pg_insert(m.UserProfile).values(**u).on_conflict_do_nothing()
            await s.execute(stmt)
        await s.commit()
    created["users"] = len(users_data)

    # ═══════════════════════════════════════════════════════════
    # 2. PROJECT + PLANTS
    # ═══════════════════════════════════════════════════════════
    async with AsyncSessionLocal() as s:
        if not await s.get(m.Project, "PRJ-DEMO-001"):
            s.add(m.Project(
                id="PRJ-DEMO-001", code="APEX-CDU-2026", name="Apex Refinery — CDU Upgrade 2026",
                description="Annual maintenance and capacity upgrade for Crude Distillation Unit and VDU",
                type="Industrial", phase="Operations", status="Active",
                location="Apex Refinery, Navi Mumbai",
                plant_ids=["PLT-DEMO-CDU", "PLT-DEMO-VDU"],
                manager_id="USR-DEMO-006", start_date="2026-01-01", end_date="2026-12-31",
                created_by="USR-DEMO-006",
            ))
        for plant_data in [
            {"id": "PLT-DEMO-CDU", "code": "CDU-04", "name": "Crude Distillation Unit 4",
             "project_id": "PRJ-DEMO-001", "type": "Process Unit", "location": "Unit 4 — North Block",
             "area": "North Process Area", "description": "Primary crude distillation with 250 m³/hr capacity",
             "equipment_ids": ["P-101", "P-202", "HX-201", "V-301"], "status": "Operational",
             "responsible_person_id": "USR-DEMO-003"},
            {"id": "PLT-DEMO-VDU", "code": "VDU-05", "name": "Vacuum Distillation Unit 5",
             "project_id": "PRJ-DEMO-001", "type": "Process Unit", "location": "Unit 5 — South Block",
             "area": "South Process Area", "description": "Vacuum distillation for heavy crude fractions",
             "equipment_ids": ["K-401", "G-101"], "status": "Operational",
             "responsible_person_id": "USR-DEMO-003"},
        ]:
            if not await s.get(m.Plant, plant_data["id"]):
                s.add(m.Plant(**plant_data))
        await s.commit()
    created["project+plants"] = 3

    # ═══════════════════════════════════════════════════════════
    # 3. EQUIPMENT (6 pieces, varied health)
    # ═══════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════
    # 4. COMPLIANCE (one record per equipment)
    # ═══════════════════════════════════════════════════════════
    compliance_data = [
        {"equipment_id": "P-101", "overall_score": 78, "status": "Warning",
         "issues": [
             {"id": "CI-P101-1", "item": "OISD-117 Sec 8.3: Alarm response time exceeded — 4hrs without shutdown", "severity": "High", "standard": "OISD-117"},
             {"id": "CI-P101-2", "item": "ISO 10816-7: Vibration in Zone C — immediate action required", "severity": "High", "standard": "ISO 10816-7"},
             {"id": "CI-P101-3", "item": "Lubrication interval 42d — SOP-P101-BEARING requires ≤30d", "severity": "Medium", "standard": "SOP-P101-BEARING"},
         ],
         "passed": [
             {"item": "OISD-117 Sec 4.1: PTW procedure in place"},
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

    # ═══════════════════════════════════════════════════════════
    # 5. SPARE PARTS
    # ═══════════════════════════════════════════════════════════
    spare_parts_data = [
        {"id": "SP-DEMO-001", "name": "SKF Bearing 6311 (Deep Groove)", "part_number": "SKF-6311-2RS",
         "equipment_ids": ["P-101", "P-202"], "quantity_on_hand": 3, "reorder_point": 2,
         "lead_time_days": 7, "location": "Warehouse A — Rack 4", "unit_cost_usd": 280,
         "status": "Available"},
        {"id": "SP-DEMO-002", "name": "John Crane Mechanical Seal 8B-1 Type-2", "part_number": "JC-8B1-T2",
         "equipment_ids": ["P-101", "P-202"], "quantity_on_hand": 1, "reorder_point": 2,
         "lead_time_days": 14, "location": "Warehouse A — Rack 5", "unit_cost_usd": 3200,
         "status": "Low Stock"},
        {"id": "SP-DEMO-003", "name": "HX-201 Tube Bundle Gasket Set", "part_number": "GEA-HX450-GS",
         "equipment_ids": ["HX-201"], "quantity_on_hand": 2, "reorder_point": 1,
         "lead_time_days": 21, "location": "Warehouse B — Row 2", "unit_cost_usd": 1850,
         "status": "Available"},
        {"id": "SP-DEMO-004", "name": "K-401 Inlet Filter Element", "part_number": "AC-ZH350-FE",
         "equipment_ids": ["K-401"], "quantity_on_hand": 4, "reorder_point": 3,
         "lead_time_days": 5, "location": "Warehouse B — Row 6", "unit_cost_usd": 450,
         "status": "Available"},
    ]
    async with AsyncSessionLocal() as s:
        for sp in spare_parts_data:
            if not await s.get(m.SparePart, sp["id"]):
                s.add(m.SparePart(**sp))
        await s.commit()
    created["spare_parts"] = len(spare_parts_data)

    # ═══════════════════════════════════════════════════════════
    # 6. LEGACY INCIDENTS (AI / system generated — for knowledge graph & AI similarity)
    # ═══════════════════════════════════════════════════════════
    legacy_incidents = [
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
    for inc in legacy_incidents:
        await db.upsert_incident(inc)
        await db.upsert_graph_node({"id": inc["id"], "name": f"Incident\n{inc['equipment_id']}\n{inc['severity']}", "type": "incident", "val": 14})
        await db.add_graph_link(inc["equipment_id"], inc["id"], "HAS_INCIDENT")
        await vs.index_incident(
            incident_id=inc["id"], title=inc["title"], description=inc["symptom"],
            equipment_id=inc["equipment_id"], severity=inc["severity"], date=inc["date"]
        )
    # Link similar incidents
    await db.add_graph_link("INC-2022-034", "INC-2023-067", "SIMILAR_PATTERN")
    created["legacy_incidents"] = len(legacy_incidents)

    # ═══════════════════════════════════════════════════════════
    # 7. INCIDENT REPORTS (formal workflow)
    # ═══════════════════════════════════════════════════════════
    incident_reports_data = [
        {"id": "IR-DEMO-P101-01", "incident_number": "INC-2026-0042",
         "title": "P-101 vibration alarm — potential bearing failure",
         "description": "Vibration on DE side reached 7.4 mm/s exceeding 7.1 mm/s alarm. Bearing temp elevated to 78°C.",
         "incident_type": "near_miss", "severity": "P2", "status": "investigation",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["P-101"],
         "occurred_at": _d(2), "reported_at": _d(2), "reported_by_name": "Rajesh Kumar",
         "investigation_lead_name": "Priya Nair",
         "investigation_team": [{"name": "Dr. Anand Sharma", "role": "quality_inspector"}],
         "immediate_actions": ["Reduced pump speed to 80% BEP", "Increased monitoring frequency to 2hr"],
         "downtime_hours": 0.0, "cost_usd": 0.0, "root_cause_category": "Mechanical"},
        {"id": "IR-DEMO-P202-01", "incident_number": "INC-2026-0039",
         "title": "P-202 seal flush leakage detected",
         "description": "API seal chamber pressure dropped to 3.2 bar (normal 4.0 bar). Flush leakage visible at Plan 11 piping.",
         "incident_type": "first_aid", "severity": "P3", "status": "root_cause_analysis",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["P-202"],
         "occurred_at": _d(7), "reported_at": _d(7), "reported_by_name": "Amit Shah",
         "investigation_lead_name": "Priya Nair",
         "root_causes": [
             {"level": 1, "cause": "Mechanical seal O-ring hardening after 38 months service", "category": "Wear"},
             {"level": 2, "cause": "Seal replacement interval not enforced in CMMS", "category": "Process"},
         ],
         "contributing_factors": ["No automated maintenance reminder", "Seal age tracking manual"],
         "downtime_hours": 6.0, "cost_usd": 8500.0, "root_cause_category": "Wear"},
        {"id": "IR-DEMO-K401-01", "incident_number": "INC-2026-0031",
         "title": "K-401 discharge pressure below normal — performance degradation",
         "description": "Compressor discharge pressure dropped to 10.8 bar (rated 12.5 bar). No change in suction conditions.",
         "incident_type": "property_damage", "severity": "P4", "status": "capa",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-VDU", "equipment_ids": ["K-401"],
         "occurred_at": _d(14), "reported_at": _d(14), "reported_by_name": "Ahmed Khan",
         "root_causes": [{"level": 1, "cause": "Inlet filter choked — 14% capacity reduction", "category": "Maintenance"}],
         "capa_items": [
             {"id": "CAPA-K401-1", "type": "corrective", "description": "Replace inlet filter immediately",
              "assigned_to_name": "Ahmed Khan", "due_date": _d(-1), "status": "completed",
              "completed_at": _d(-1)},
             {"id": "CAPA-K401-2", "type": "preventive", "description": "Reduce filter change interval to 60 days",
              "assigned_to_name": "Ahmed Khan", "due_date": _d(-14), "status": "open"},
         ],
         "downtime_hours": 4.0, "cost_usd": 2200.0, "root_cause_category": "Maintenance"},
    ]
    async with AsyncSessionLocal() as s:
        for ir in incident_reports_data:
            existing = await s.get(m.IncidentReport, ir["id"])
            if not existing:
                s.add(m.IncidentReport(**ir))
        await s.commit()
    for ir in incident_reports_data:
        await db.upsert_graph_node({"id": ir["id"], "name": f"IncRpt\n{ir['severity']}\n{ir['status']}", "type": "incident", "val": 14})
        for eq_id in (ir.get("equipment_ids") or []):
            await db.add_graph_link(eq_id, ir["id"], "HAS_INCIDENT")
        await vs.index_incident(ir["id"], ir["title"], ir["description"],
                                (ir.get("equipment_ids") or [""])[0], ir["severity"])
    created["incident_reports"] = len(incident_reports_data)

    # ═══════════════════════════════════════════════════════════
    # 8. MAINTENANCE RECORDS
    # ═══════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════
    # 9. MANAGED WORK ORDERS (4 different stages)
    # ═══════════════════════════════════════════════════════════
    mwo_data = [
        {"id": "MWO-DEMO-P101", "wo_number": "WO-2026-0042", "title": "P-101 DE bearing replacement",
         "description": "Replace drive-end bearing following vibration alarm. Vibration reached 7.4 mm/s (alarm 7.1).",
         "category": "corrective", "priority": "high", "status": "approved",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["P-101"],
         "estimated_hours": 4.0, "created_by_name": "Rajesh Kumar",
         "approver_name": "Ahmed Khan", "approval_decision": "approved", "approval_date": _d(1),
         "tasks": [
             {"seq": 1, "title": "Isolate and LOTO pump", "trade": "mechanical", "estimated_hours": 0.5, "status": "pending"},
             {"seq": 2, "title": "Remove bearing housing", "trade": "mechanical", "estimated_hours": 0.75, "status": "pending"},
             {"seq": 3, "title": "Replace SKF 6311 bearing", "trade": "mechanical", "estimated_hours": 1.0, "status": "pending"},
             {"seq": 4, "title": "Reassemble and alignment check", "trade": "mechanical", "estimated_hours": 1.25, "status": "pending"},
             {"seq": 5, "title": "Functional test and sign-off", "trade": "mechanical", "estimated_hours": 0.5, "status": "pending"},
         ],
         "materials": [{"part_number": "SKF-6311-2RS", "description": "Deep groove ball bearing", "qty_required": 1, "qty_issued": 0}],
         "safety_requirements": ["LOTO procedure applied", "PTW hot class C required"]},
        {"id": "MWO-DEMO-P202", "wo_number": "WO-2026-0039", "title": "P-202 mechanical seal replacement",
         "description": "Replace mechanical seal following leakage report. Seal age 38 months.",
         "category": "corrective", "priority": "medium", "status": "in_progress",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["P-202"],
         "estimated_hours": 6.0, "actual_hours": 3.5, "created_by_name": "Amit Shah",
         "approver_name": "Ahmed Khan", "approval_decision": "approved", "approval_date": _d(5),
         "started_by_name": "Rajesh Kumar", "started_at": _d(1),
         "tasks": [
             {"seq": 1, "title": "Drain and flush seal chamber", "trade": "mechanical", "status": "completed"},
             {"seq": 2, "title": "Remove old seal assembly", "trade": "mechanical", "status": "completed"},
             {"seq": 3, "title": "Install John Crane 8B-1 Type-2", "trade": "mechanical", "status": "in_progress"},
             {"seq": 4, "title": "Pressure test seal system", "trade": "mechanical", "status": "pending"},
         ],
         "materials": [{"part_number": "JC-8B1-T2", "description": "Mechanical seal Type-2", "qty_required": 1, "qty_issued": 1}]},
        {"id": "MWO-DEMO-K401", "wo_number": "WO-2026-0031", "title": "K-401 annual overhaul",
         "description": "Annual preventive maintenance for process air compressor. Replace filter, check valves, calibrate instruments.",
         "category": "preventive", "priority": "medium", "status": "scheduled",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-VDU", "equipment_ids": ["K-401"],
         "estimated_hours": 16.0, "scheduled_start": _d(-7), "scheduled_end": _d(-5),
         "created_by_name": "Ahmed Khan", "approver_name": "Ahmed Khan",
         "tasks": [
             {"seq": 1, "title": "Filter element replacement", "status": "pending"},
             {"seq": 2, "title": "Suction valve inspection", "status": "pending"},
             {"seq": 3, "title": "Discharge valve inspection", "status": "pending"},
             {"seq": 4, "title": "Instrument calibration", "status": "pending"},
         ]},
        {"id": "MWO-DEMO-G101", "wo_number": "WO-2026-0021", "title": "G-101 fan blade erosion coating",
         "description": "Apply erosion-resistant coating to fan blades per Howden OEM recommendation.",
         "category": "preventive", "priority": "low", "status": "closed",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-VDU", "equipment_ids": ["G-101"],
         "estimated_hours": 8.0, "actual_hours": 9.5, "created_by_name": "Ahmed Khan",
         "approver_name": "Ahmed Khan", "approval_decision": "approved",
         "completed_by_name": "Rajesh Kumar", "completed_at": _d(21),
         "completion_notes": "Epoxy ceramic coating applied to all 6 blades. Vibration checked — 2.8 mm/s normal.",
         "verified_by_name": "Dr. Anand Sharma", "verification_decision": "passed", "verified_at": _d(20)},
    ]
    async with AsyncSessionLocal() as s:
        for wo in mwo_data:
            existing = await s.get(m.ManagedWorkOrder, wo["id"])
            if not existing:
                s.add(m.ManagedWorkOrder(**wo))
        await s.commit()
    for wo in mwo_data:
        await db.upsert_graph_node({"id": wo["id"], "name": f"MWO\n{wo['priority']}\n{wo['status']}", "type": "work_order", "val": 14})
        for eq_id in (wo.get("equipment_ids") or []):
            await db.add_graph_link(eq_id, wo["id"], "HAS_WORK_ORDER")
    created["managed_work_orders"] = len(mwo_data)

    # ═══════════════════════════════════════════════════════════
    # 10. PERMITS TO WORK (3 states)
    # ═══════════════════════════════════════════════════════════
    ptw_data = [
        {"id": "PTW-DEMO-P101-01", "permit_number": "PTW-2026-0042",
         "permit_type": "cold_work", "title": "P-101 bearing replacement — Unit 4 CDU",
         "scope_of_work": "Remove and replace drive-end bearing. Isolate suction MOV-101A and discharge MOV-101B.",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["P-101"],
         "work_order_id": "MWO-DEMO-P101", "status": "issued",
         "planned_start": TODAY, "planned_end": TODAY,
         "hazards": [
             {"hazard": "Rotating machinery", "likelihood": "High", "severity": "Critical", "mitigation": "LOTO applied and verified"},
             {"hazard": "Confined space near bearing housing", "likelihood": "Low", "severity": "High", "mitigation": "Ventilation confirmed"},
         ],
         "isolation_points": [
             {"tag_number": "MOV-101A", "description": "Suction valve", "isolation_type": "valve_closed", "verified_by": "Suresh Patel"},
             {"tag_number": "MOV-101B", "description": "Discharge valve", "isolation_type": "valve_closed", "verified_by": "Suresh Patel"},
         ],
         "ppe_requirements": [{"item": "Safety glasses"}, {"item": "Safety boots"}, {"item": "Nitrile gloves"}],
         "originator_name": "Rajesh Kumar", "originator_date": _d(1),
         "area_authority_name": "Suresh Patel", "area_authority_decision": "approved", "area_authority_date": _d(1),
         "safety_officer_name": "Priya Nair", "safety_officer_decision": "approved", "safety_officer_date": _d(1),
         "ap_name": "Ahmed Khan", "ap_decision": "approved", "ap_issue_date": TODAY,
         "created_by": "Rajesh Kumar"},
        {"id": "PTW-DEMO-HX201-01", "permit_number": "PTW-2026-0038",
         "permit_type": "hot_work", "title": "HX-201 tube plug welding — Unit 4",
         "scope_of_work": "Weld plug two failed tubes in HX-201 shell and tube heat exchanger.",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["HX-201"],
         "status": "area_authority_review", "planned_start": _d(-2), "planned_end": _d(-1),
         "hazards": [
             {"hazard": "Hot work in hazardous area", "likelihood": "Medium", "severity": "Critical", "mitigation": "Fire watch assigned, fire extinguisher positioned"},
             {"hazard": "Hydrocarbon vapour", "likelihood": "Medium", "severity": "Critical", "mitigation": "Gas test clear < 1% LEL"},
         ],
         "gas_tests": [{"tested_by": "Priya Nair", "test_time": _d(-2), "result": "Clear", "gas": "H2S", "ppm": 0, "lel_percent": 0.4}],
         "originator_name": "Amit Shah", "originator_date": _d(3),
         "area_authority_name": "Suresh Patel", "area_authority_decision": None,
         "created_by": "Amit Shah"},
        {"id": "PTW-DEMO-V301-01", "permit_number": "PTW-2026-0025",
         "permit_type": "confined_space", "title": "V-301 internal inspection",
         "scope_of_work": "Entry into V-301 surge drum for internal visual inspection and thickness survey.",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["V-301"],
         "status": "closed", "planned_start": _d(30), "planned_end": _d(28),
         "actual_start": _d(30), "actual_end": _d(28),
         "gas_tests": [{"tested_by": "Priya Nair", "test_time": _d(30), "result": "Clear", "gas": "O2", "ppm": 20.9, "lel_percent": 0.0}],
         "originator_name": "Dr. Anand Sharma", "originator_date": _d(32),
         "area_authority_name": "Suresh Patel", "area_authority_decision": "approved", "area_authority_date": _d(31),
         "safety_officer_name": "Priya Nair", "safety_officer_decision": "approved",
         "ap_name": "Ahmed Khan", "ap_decision": "approved", "ap_issue_date": _d(30), "ap_close_date": _d(28),
         "closure_comments": "Inspection completed. 2 minor corrosion spots noted. Action items raised.",
         "created_by": "Dr. Anand Sharma"},
    ]
    async with AsyncSessionLocal() as s:
        for ptw in ptw_data:
            existing = await s.get(m.PermitToWork, ptw["id"])
            if not existing:
                s.add(m.PermitToWork(**ptw))
        await s.commit()
    for ptw in ptw_data:
        await db.upsert_graph_node({"id": ptw["id"], "name": f"PTW\n{ptw['permit_type']}\n{ptw['status']}", "type": "work_order", "val": 13})
        for eq_id in (ptw.get("equipment_ids") or []):
            await db.add_graph_link(eq_id, ptw["id"], "HAS_WORK_ORDER")
    created["permits_to_work"] = len(ptw_data)

    # ═══════════════════════════════════════════════════════════
    # 11. SAFETY PROCEDURES
    # ═══════════════════════════════════════════════════════════
    proc_data = [
        {"id": "SP-DEMO-BEAR", "code": "SOP-P101-BEARING", "title": "P-101 Bearing Replacement Procedure",
         "doc_type": "SOP", "category": "Mechanical", "version": "2.1", "risk_level": "High",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["P-101", "P-202"],
         "status": "active", "effective_date": "2024-01-15", "review_due_date": "2026-01-15",
         "author_name": "Priya Nair", "authored_date": "2023-12-01",
         "peer_reviewer_name": "Dr. Anand Sharma", "peer_review_decision": "approved",
         "tech_reviewer_name": "Ahmed Khan", "tech_review_decision": "approved",
         "approver_name": "Deepa Menon", "approver_decision": "approved", "approval_date": "2024-01-10",
         "steps": [
             {"step_number": 1, "title": "Obtain and issue PTW", "description": "Apply for cold work PTW. Ensure LOTO.", "responsible_role": "supervisor"},
             {"step_number": 2, "title": "Isolate energy sources", "description": "Close MOV-101A and MOV-101B. Apply lockout devices.", "responsible_role": "technician"},
             {"step_number": 3, "title": "Drain and cool", "description": "Drain pump casing. Allow to cool to <40°C.", "responsible_role": "technician"},
             {"step_number": 4, "title": "Remove bearing housing", "description": "Uncouple motor. Remove bearing housing per OEM Fig 3.2.", "responsible_role": "technician"},
             {"step_number": 5, "title": "Replace bearing", "description": "Press fit new SKF 6311 bearing. Apply 50g LGMT-2 grease.", "responsible_role": "technician"},
             {"step_number": 6, "title": "Reassemble and test", "description": "Realign coupling to <0.05mm. Run at low load for 2 hrs.", "responsible_role": "supervisor"},
         ],
         "ppe_requirements": [{"item": "Safety glasses"}, {"item": "Safety boots"}, {"item": "Gloves"}]},
        {"id": "SP-DEMO-HWJSA", "code": "JSA-HOT-WORK-2026", "title": "Hot Work Job Safety Analysis — Refinery",
         "doc_type": "JSA", "category": "Process", "version": "1.3", "risk_level": "Critical",
         "plant_id": "PLT-DEMO-CDU", "status": "peer_review",
         "author_name": "Priya Nair", "authored_date": _d(10),
         "peer_reviewer_name": "Suresh Patel",
         "hazard_register": [
             {"hazard": "Ignition of flammable vapours", "risk_before": "Critical", "risk_after": "Medium", "control_measure": "Continuous gas monitoring, hot work permit, fire watch"},
             {"hazard": "Arc flash / electric shock", "risk_before": "High", "risk_after": "Low", "control_measure": "Insulated PPE, LOTO applied"},
         ]},
        {"id": "SP-DEMO-COMP-SOP", "code": "SOP-K401-OVERHAUL", "title": "K-401 Compressor Annual Maintenance SOP",
         "doc_type": "SOP", "category": "Mechanical", "version": "1.0", "risk_level": "High",
         "plant_id": "PLT-DEMO-VDU", "equipment_ids": ["K-401"], "status": "draft",
         "author_name": "Ahmed Khan", "authored_date": _d(5)},
    ]
    async with AsyncSessionLocal() as s:
        for sp in proc_data:
            existing = await s.get(m.SafetyProcedure, sp["id"])
            if not existing:
                s.add(m.SafetyProcedure(**sp))
        await s.commit()
    for sp in proc_data:
        await db.upsert_graph_node({"id": sp["id"], "name": f"SOP\n{sp['code'][:16]}", "type": "safety_procedure", "val": 13})
        for eq_id in (sp.get("equipment_ids") or []):
            await db.add_graph_link(sp["id"], eq_id, "GOVERNS")
    created["safety_procedures"] = len(proc_data)

    # ═══════════════════════════════════════════════════════════
    # 12. QUALITY INSPECTIONS
    # ═══════════════════════════════════════════════════════════
    insp_data = [
        {"id": "QI-DEMO-P101-PRE", "inspection_number": "QI-2026-0042",
         "title": "Pre-maintenance inspection — P-101 bearing replacement",
         "inspection_type": "equipment", "status": "scheduled",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["P-101"],
         "priority": "high", "scheduled_date": TODAY, "inspector_name": "Dr. Anand Sharma",
         "checklist_items": [
             {"seq": 1, "check_item": "Vibration level current reading", "criteria": "Log and compare with alarm (7.1 mm/s)"},
             {"seq": 2, "check_item": "Bearing housing temperature", "criteria": "< 75°C alarm threshold"},
             {"seq": 3, "check_item": "Shaft runout measurement", "criteria": "< 0.05 mm"},
             {"seq": 4, "check_item": "LOTO status verification", "criteria": "All lock devices applied and tagged"},
         ],
         "created_by": "Dr. Anand Sharma"},
        {"id": "QI-DEMO-K401-ANN", "inspection_number": "QI-2026-0031",
         "title": "K-401 annual safety audit and performance test",
         "inspection_type": "safety_audit", "status": "in_progress",
         "plant_id": "PLT-DEMO-VDU", "equipment_ids": ["K-401"],
         "priority": "medium", "scheduled_date": _d(3), "actual_date": _d(2),
         "inspector_name": "Dr. Anand Sharma",
         "checklist_items": [
             {"seq": 1, "check_item": "Safety relief valve set pressure", "criteria": "13.5 bar ±2%", "result": "pass", "findings": "Set at 13.4 bar — OK"},
             {"seq": 2, "check_item": "Discharge pressure at rated flow", "criteria": "12.5 bar", "result": "fail", "findings": "10.8 bar — 14% below rated. Filter choked."},
             {"seq": 3, "check_item": "Vibration within ISO zone", "criteria": "Zone A/B (< 3.5 mm/s)", "result": "obs", "findings": "4.2 mm/s — Zone B approaching C"},
         ],
         "non_conformances": [
             {"id": "NC-K401-01", "description": "Discharge pressure 14% below rated — compressor performance degraded",
              "severity": "major", "action_required": "Investigate root cause, replace filter, retest",
              "due_date": _d(-3), "status": "open"},
         ],
         "overall_score": 66.7, "created_by": "Dr. Anand Sharma"},
        {"id": "QI-DEMO-HX201-01", "inspection_number": "QI-2026-0025",
         "title": "HX-201 tube bundle API 660 inspection",
         "inspection_type": "equipment", "status": "closed_with_findings",
         "plant_id": "PLT-DEMO-CDU", "equipment_ids": ["HX-201"],
         "priority": "medium", "scheduled_date": _d(90), "actual_date": _d(88),
         "inspector_name": "Dr. Anand Sharma",
         "checklist_items": [
             {"seq": 1, "check_item": "Tube wall thickness survey", "criteria": "> 80% nominal", "result": "pass", "findings": "Min 85% nominal — acceptable"},
             {"seq": 2, "check_item": "Tube plugging count", "criteria": "< 10% of total tubes", "result": "pass", "findings": "2/450 tubes plugged = 0.44%"},
         ],
         "non_conformances": [
             {"id": "NC-HX201-01", "description": "2 tubes showing early erosion-corrosion — monitor quarterly",
              "severity": "minor", "action_required": "Add to quarterly inspection roster", "status": "open"},
         ],
         "overall_score": 85.0, "summary_notes": "Shell side fouled — cleaned. 2 tubes plugged and quarantine-marked.",
         "reviewer_name": "Deepa Menon", "reviewer_decision": "closed_with_findings",
         "created_by": "Dr. Anand Sharma"},
    ]
    async with AsyncSessionLocal() as s:
        for insp in insp_data:
            existing = await s.get(m.QualityInspection, insp["id"])
            if not existing:
                s.add(m.QualityInspection(**insp))
        await s.commit()
    for insp in insp_data:
        await db.upsert_graph_node({"id": insp["id"], "name": f"Inspection\n{insp['inspection_type']}", "type": "inspection", "val": 13})
        for eq_id in (insp.get("equipment_ids") or []):
            await db.add_graph_link(insp["id"], eq_id, "COVERS")
    created["quality_inspections"] = len(insp_data)

    # ═══════════════════════════════════════════════════════════
    # 13. ACTION ITEMS (CAPA)
    # ═══════════════════════════════════════════════════════════
    actions_data = [
        {"id": "ACT-DEMO-001", "action_number": "ACT-2026-001",
         "title": "Reduce P-101 lubrication interval to 14 days",
         "description": "Update SOP-P101-BEARING: reduce grease interval from 30 to 14 days following bearing failure root cause analysis.",
         "source_type": "incident", "source_id": "IR-DEMO-P101-01", "source_ref": "INC-2026-0042",
         "action_type": "preventive", "priority": "high", "status": "open",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU",
         "assigned_to_name": "Rajesh Kumar", "due_date": _d(-7), "created_by": "Priya Nair"},
        {"id": "ACT-DEMO-002", "action_number": "ACT-2026-002",
         "title": "Install automated vibration alert for P-101 and P-202",
         "description": "Connect vibration sensors to DCS alarm system. Configure SMS alert for values >6.5 mm/s.",
         "source_type": "inspection", "source_id": "QI-DEMO-K401-ANN", "source_ref": "QI-2026-0031",
         "action_type": "improvement", "priority": "medium", "status": "in_progress",
         "project_id": "PRJ-DEMO-001", "plant_id": "PLT-DEMO-CDU",
         "assigned_to_name": "Ahmed Khan", "due_date": _d(-30), "created_by": "Dr. Anand Sharma",
         "completion_evidence": "DCS wiring completed. SMS gateway configured. Testing in progress."},
        {"id": "ACT-DEMO-003", "action_number": "ACT-2026-003",
         "title": "Update emergency shutdown procedure for K-401",
         "description": "Revise ESD procedure to include compressor performance threshold checks before manual shutdown.",
         "source_type": "observation", "source_id": "QI-DEMO-K401-ANN", "source_ref": "QI-2026-0031",
         "action_type": "corrective", "priority": "low", "status": "open",
         "plant_id": "PLT-DEMO-VDU",
         "assigned_to_name": "Priya Nair", "due_date": _d(-60), "created_by": "Deepa Menon"},
    ]
    async with AsyncSessionLocal() as s:
        for act in actions_data:
            existing = await s.get(m.ActionItem, act["id"])
            if not existing:
                s.add(m.ActionItem(**act))
        await s.commit()
    created["action_items"] = len(actions_data)

    # ═══════════════════════════════════════════════════════════
    # 14. SENSOR HISTORY (30-day trending data for P-101 and K-401)
    # ═══════════════════════════════════════════════════════════
    import math, random
    random.seed(42)  # deterministic

    p101_vib_readings = []
    for day in range(30, 0, -1):
        ts = (datetime.utcnow() - timedelta(days=day)).isoformat()
        # Vibration trending up over 30 days: 4.0 → 7.4
        base = 4.0 + (30 - day) * (3.4 / 30)
        noise = random.uniform(-0.15, 0.15)
        p101_vib_readings.append({"ts": ts, "value": round(base + noise, 2), "unit": "mm/s"})
    await db.upsert_sensor_history("P-101", "vibration_de", p101_vib_readings)

    k401_pres_readings = []
    for day in range(30, 0, -1):
        ts = (datetime.utcnow() - timedelta(days=day)).isoformat()
        # Pressure declining: 12.4 → 10.8
        base = 12.4 - (30 - day) * (1.6 / 30)
        noise = random.uniform(-0.08, 0.08)
        k401_pres_readings.append({"ts": ts, "value": round(base + noise, 2), "unit": "bar"})
    await db.upsert_sensor_history("K-401", "discharge_pressure", k401_pres_readings)
    created["sensor_history"] = "P-101 vibration + K-401 pressure (30d)"

    # ═══════════════════════════════════════════════════════════
    # 15. KNOWLEDGE GRAPH — Project / Plant nodes + links
    # ═══════════════════════════════════════════════════════════
    await db.upsert_graph_node({"id": "PRJ-DEMO-001", "name": "Project\nApex CDU 2026", "type": "project", "val": 20})
    await db.upsert_graph_node({"id": "PLT-DEMO-CDU", "name": "Plant\nCDU Unit 4", "type": "plant", "val": 18})
    await db.upsert_graph_node({"id": "PLT-DEMO-VDU", "name": "Plant\nVDU Unit 5", "type": "plant", "val": 18})
    await db.add_graph_link("PLT-DEMO-CDU", "PRJ-DEMO-001", "BELONGS_TO")
    await db.add_graph_link("PLT-DEMO-VDU", "PRJ-DEMO-001", "BELONGS_TO")
    for eq_id in ["P-101", "P-202", "HX-201", "V-301"]:
        await db.add_graph_link(eq_id, "PLT-DEMO-CDU", "LOCATED_IN")
    for eq_id in ["K-401", "G-101"]:
        await db.add_graph_link(eq_id, "PLT-DEMO-VDU", "LOCATED_IN")
    # Downstream flow chain
    await db.add_graph_link("P-101", "HX-201", "FEEDS")
    await db.add_graph_link("HX-201", "V-301", "FEEDS")
    created["graph_nodes+links"] = "project+plants+equipment+incidents+WOs"

    # ═══════════════════════════════════════════════════════════
    # 16. DEMO DOCUMENTS — generate files on disk only (not in DB)
    #     User uploads them via /documents to run the AI pipeline
    # ═══════════════════════════════════════════════════════════
    from app.services.demo_docs import generate_demo_documents
    doc_records = generate_demo_documents()
    # Build list of {filename, doc_id} for the UI — do NOT insert into DB
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
            "4 legacy incidents with similarity patterns for AI learning",
            "3 incident reports across full investigation lifecycle",
            "4 work orders at draft/approved/in_progress/closed stages",
            "3 PTWs at different approval stages",
            "Active SOP + draft JSA + peer-review procedure",
        ],
    }
