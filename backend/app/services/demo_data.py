"""
AI Operations Brain — Demo Data
Rich, realistic industrial dataset for the Pump P-101 hackathon scenario.
Provides the knowledge needed by all five agents without external dependencies.
"""
from datetime import datetime, date
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# EQUIPMENT REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

EQUIPMENT: dict[str, dict[str, Any]] = {
    "P-101": {
        "id": "P-101",
        "name": "Crude Oil Feed Pump",
        "type": "Centrifugal Pump",
        "subtype": "API 610 Type BB1",
        "location": "Unit 4 — CDU (Crude Distillation Unit)",
        "area": "Pump House A",
        "installed_date": "2018-03-12",
        "manufacturer": "Flowserve Corporation",
        "model": "PVXM-100",
        "serial_number": "FS-2018-4412",
        "health_score": 72,
        "failure_probability": 18,
        "compliance_score": 85,
        "maintenance_due_days": 7,
        "criticality": "High",
        "last_inspection_date": "2026-04-15",
        "next_inspection_date": "2026-07-27",
        "technicians": ["Rajesh Kumar", "Amit Shah", "Priya Nair"],
        "supervisor": "S. Venkataraman",
        "specifications": {
            "rated_flow": "250 m³/hr",
            "rated_head": "85 m",
            "motor_power": "75 kW",
            "rated_rpm": "2960",
            "operating_temp": "-20°C to 120°C",
            "design_pressure": "8.5 bar",
            "npshr": "3.2 m",
            "efficiency": "82%",
            "fluid": "Crude oil (API 35°, 65°C)",
            "seal_type": "Mechanical Seal Type-2 (Plan 11)",
            "bearing_type": "SKF 6311",
            "coupling": "Flexible disc coupling",
        },
        "current_readings": {
            "vibration_de": {"value": 7.2, "unit": "mm/s", "normal": 4.5, "alarm": 7.1, "trip": 11.2},
            "vibration_nde": {"value": 5.8, "unit": "mm/s", "normal": 4.5, "alarm": 7.1, "trip": 11.2},
            "bearing_temp_de": {"value": 68, "unit": "°C", "normal": 55, "alarm": 75, "trip": 90},
            "bearing_temp_nde": {"value": 62, "unit": "°C", "normal": 55, "alarm": 75, "trip": 90},
            "discharge_pressure": {"value": 7.8, "unit": "bar", "normal": 8.5},
            "flow_rate": {"value": 238, "unit": "m³/hr", "normal": 250},
            "motor_current": {"value": 42.3, "unit": "A", "normal": 45},
        },
        "downstream_equipment": ["HX-201", "V-301"],
        "upstream_equipment": ["T-001"],
        "p_and_id": "PID-CDU-001-Rev4",
        "iso_tag": "P-101A/B",
        "status": "Running",
    },
    "P-202": {
        "id": "P-202",
        "name": "Atmospheric Residue Pump",
        "type": "Centrifugal Pump",
        "subtype": "API 610 Type OH2",
        "location": "Unit 4 — CDU",
        "area": "Pump House A",
        "installed_date": "2019-07-20",
        "manufacturer": "Flowserve Corporation",
        "model": "PVXM-80",
        "health_score": 91,
        "failure_probability": 4,
        "compliance_score": 96,
        "maintenance_due_days": 45,
        "criticality": "High",
        "last_incident": "INC-2023-067",
        "specifications": {
            "rated_flow": "180 m³/hr",
            "rated_head": "70 m",
            "motor_power": "55 kW",
        },
        "current_readings": {
            "vibration_de": {"value": 3.1, "unit": "mm/s", "normal": 4.5, "alarm": 7.1, "trip": 11.2},
            "bearing_temp_de": {"value": 51, "unit": "°C", "normal": 55, "alarm": 75},
        },
        "status": "Running",
    },
    "HX-201": {
        "id": "HX-201",
        "name": "Crude Feed Pre-heater",
        "type": "Heat Exchanger",
        "subtype": "Shell and Tube",
        "location": "Unit 4 — CDU",
        "health_score": 88,
        "failure_probability": 7,
        "compliance_score": 92,
        "maintenance_due_days": 22,
        "criticality": "High",
        "status": "Running",
        "upstream_equipment": ["P-101"],
        "downstream_equipment": ["V-301"],
    },
    "V-301": {
        "id": "V-301",
        "name": "Crude Feed Surge Drum",
        "type": "Pressure Vessel",
        "subtype": "Horizontal Drum",
        "location": "Unit 4 — CDU",
        "health_score": 95,
        "failure_probability": 2,
        "compliance_score": 100,
        "maintenance_due_days": 90,
        "criticality": "Critical",
        "status": "Running",
        "upstream_equipment": ["HX-201"],
    },
    "K-401": {
        "id": "K-401",
        "name": "Process Air Compressor",
        "type": "Compressor",
        "subtype": "Reciprocating",
        "location": "Unit 5 — VDU",
        "health_score": 65,
        "failure_probability": 25,
        "compliance_score": 78,
        "maintenance_due_days": 3,
        "criticality": "High",
        "status": "Running — Alert",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# INCIDENT HISTORY
# ─────────────────────────────────────────────────────────────────────────────

INCIDENTS: list[dict[str, Any]] = [
    {
        "id": "INC-2022-034",
        "equipment_id": "P-101",
        "date": "2022-08-14",
        "title": "Drive-end bearing failure after vibration alarm",
        "severity": "High",
        "symptom": "Vibration increased from 4.2 mm/s to 8.7 mm/s over 6 hours. High-pitched noise from DE bearing.",
        "initial_reading": "8.7 mm/s (DE), normal 4.5 mm/s",
        "precursor_days": 3,
        "precursor_symptom": "Vibration trending upward over 3 days, lubrication last done 45 days prior (overdue)",
        "root_cause": "Bearing wear due to lubrication interval exceeded. Grease hardening caused inadequate film thickness.",
        "root_cause_category": "Maintenance",
        "failure_mode": "Bearing degradation → metal fatigue → complete failure",
        "downtime_hours": 12,
        "action_taken": "Emergency shutdown at 9.1 mm/s. Replaced SKF 6311 bearing on DE side. Updated lubrication SOP from 30-day to 14-day interval.",
        "lessons_learned": "Vibration alarms above 7.1 mm/s for >2 hours indicate imminent bearing failure. Same pump (P-101) with similar symptoms: bearing failure within 18 hours.",
        "cost_usd": 14200,
        "technician": "Rajesh Kumar",
        "approved_by": "S. Venkataraman",
        "keywords": ["vibration", "bearing", "lubrication", "wear", "centrifugal pump"],
        "oem_reference": "Flowserve PVXM-100 Manual — Section 4.2 Vibration Analysis",
        "regulation_violated": "OISD-117 Section 8.3 — Failure to shutdown within 2 hours of sustained alarm",
        "spare_parts_used": ["SKF Bearing 6311 (×1)", "Grease cartridge (×2)"],
    },
    {
        "id": "INC-2021-011",
        "equipment_id": "P-101",
        "date": "2021-03-22",
        "title": "Mechanical seal leakage — routine inspection find",
        "severity": "Medium",
        "symptom": "Seal flush leakage detected at Plan 11 piping. API Seal chamber pressure dropped 0.3 bar.",
        "root_cause": "Mechanical seal O-ring hardening after 30 months in service. Normal wear.",
        "root_cause_category": "Wear",
        "failure_mode": "Elastomer degradation → reduced sealing → leakage",
        "downtime_hours": 8,
        "action_taken": "Replaced complete mechanical seal assembly with upgraded Type-2 seal (John Crane 8B-1). Extended seal life from 30 to 48 months.",
        "lessons_learned": "Schedule seal inspection at 36-month mark. Type-2 seal significantly more durable.",
        "cost_usd": 8500,
        "technician": "Amit Shah",
        "keywords": ["seal", "leakage", "mechanical seal", "O-ring"],
        "oem_reference": "Flowserve PVXM-100 Manual — Section 5.1 Seal Maintenance",
    },
    {
        "id": "INC-2023-067",
        "equipment_id": "P-202",
        "date": "2023-11-08",
        "title": "Vibration spike followed by bearing failure — P-202 (similar to P-101 2022 pattern)",
        "severity": "High",
        "symptom": "Vibration increased to 7.8 mm/s, followed by complete DE bearing failure 14 hours later",
        "root_cause": "Cavitation due to inadequate NPSH margin during high-throughput operation",
        "root_cause_category": "Process",
        "failure_mode": "Cavitation → impeller erosion → shaft vibration → bearing overload → failure",
        "downtime_hours": 36,
        "action_taken": "Installed inlet strainer, adjusted operating point to 85% BEP. Reduced flow rate to 153 m³/hr.",
        "lessons_learned": "Similar vibration signature to P-101 INC-2022-034 but different root cause (cavitation vs lubrication). Both lead to bearing failure within 18 hours of sustained alarm.",
        "cost_usd": 31000,
        "technician": "Priya Nair",
        "keywords": ["vibration", "bearing", "cavitation", "NPSH", "centrifugal pump", "P-202"],
        "cross_reference": "INC-2022-034",
        "similarity_to_p101": 82,
    },
    {
        "id": "INC-2020-005",
        "equipment_id": "P-101",
        "date": "2020-01-09",
        "title": "Discharge pressure drop — impeller erosion",
        "severity": "Medium",
        "symptom": "Discharge pressure dropped from 8.5 to 6.8 bar. Flow rate reduced.",
        "root_cause": "Impeller erosion due to particulate in crude feed",
        "root_cause_category": "Process",
        "downtime_hours": 20,
        "action_taken": "Replaced impeller with Stellite-coated version. Installed Y-strainer on suction.",
        "technician": "Rajesh Kumar",
        "keywords": ["pressure", "impeller", "erosion", "flow"],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# MAINTENANCE RECORDS
# ─────────────────────────────────────────────────────────────────────────────

MAINTENANCE_RECORDS: list[dict[str, Any]] = [
    {
        "id": "MR-2026-012",
        "equipment_id": "P-101",
        "date": "2026-05-10",
        "type": "Preventive",
        "description": "Routine lubrication and vibration check — biweekly schedule",
        "vibration_de": 4.1,
        "vibration_nde": 3.9,
        "bearing_temp": 52,
        "oil_added_ml": 150,
        "technician": "Rajesh Kumar",
        "status": "Completed",
        "findings": "All within normal limits. No anomalies.",
        "next_due": "2026-05-24",
    },
    {
        "id": "MR-2026-008",
        "equipment_id": "P-101",
        "date": "2026-04-26",
        "type": "Preventive",
        "description": "Biweekly lubrication — lubrication routine",
        "vibration_de": 3.8,
        "vibration_nde": 3.6,
        "bearing_temp": 50,
        "oil_added_ml": 140,
        "technician": "Amit Shah",
        "status": "Completed",
        "findings": "Normal. Slight increase in DE vibration from last reading (3.5→3.8). Monitoring.",
    },
    {
        "id": "MR-2026-003",
        "equipment_id": "P-101",
        "date": "2026-03-22",
        "type": "Preventive",
        "description": "Annual bearing inspection and alignment check",
        "vibration_de": 3.5,
        "bearing_temp": 49,
        "technician": "Amit Shah",
        "status": "Completed",
        "findings": "Bearing clearance within specification. Alignment: 0.03mm (acceptable). Coupling inspected — no wear.",
    },
    {
        "id": "MR-2026-OVERDUE",
        "equipment_id": "P-101",
        "date": None,
        "scheduled_date": "2026-07-08",
        "type": "Preventive",
        "description": "Biweekly lubrication — OVERDUE by 12 days",
        "status": "Overdue",
        "overdue_days": 12,
        "technician": None,
        "findings": "Not performed",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────

DOCUMENTS: list[dict[str, Any]] = [
    {
        "id": "DOC-001",
        "name": "Flowserve PVXM-100 OEM Manual",
        "type": "manual",
        "equipment_ids": ["P-101", "P-202"],
        "version": "Rev 3.1",
        "date": "2022-06-01",
        "sections": {
            "4.2": "Vibration Analysis — Alarm at 7.1 mm/s. If vibration exceeds alarm for >2 continuous hours, initiate shutdown. Sustained vibration above alarm without intervention typically results in bearing failure within 12–24 hours. Root causes: bearing wear (most common), misalignment, cavitation, unbalance.",
            "4.3": "Bearing Maintenance — Relubricate every 14 days under normal conditions. Use SKF LGMT 2 grease, 150ml per bearing. Extended intervals beyond 21 days risk lubricant degradation and bearing damage.",
            "5.1": "Mechanical Seal — Inspect seal chamber pressure weekly. Type-2 seal service life: 48 months. Replace if chamber pressure drops >0.2 bar from baseline.",
            "6.1": "Troubleshooting — High vibration: Check lubrication (most common), check alignment (laser align if >0.05mm), check NPSH margin, check coupling.",
            "7.1": "Spare Parts — Minimum stock: SKF 6311 bearing ×2, John Crane 8B-1 seal ×1, coupling insert ×1.",
        },
        "key_warnings": [
            "DANGER: Do not operate above trip threshold (11.2 mm/s). Immediate seizure risk.",
            "WARNING: Vibration >7.1 mm/s for >2 hours indicates bearing failure within 12–24 hours.",
        ],
    },
    {
        "id": "DOC-002",
        "name": "SOP-P-001: Centrifugal Pump Operations & Emergency Shutdown",
        "type": "sop",
        "equipment_ids": ["P-101", "P-202"],
        "version": "Rev 2.3",
        "date": "2025-01-15",
        "sections": {
            "3.1": "Normal Operation — Monitor vibration every 4 hours. Log readings in CMMS.",
            "4.1": "Emergency Shutdown Procedure — 1. Notify supervisor immediately. 2. Issue PTW (Permit to Work). 3. Isolate suction MOV-101A and discharge MOV-101B. 4. Allow pump to coast to stop (do not brake). 5. Lock out/tag out. 6. Call maintenance team.",
            "4.2": "Vibration Alarm Response — >7.1 mm/s: Increase monitoring frequency to 30 min, notify supervisor. Schedule maintenance within 24 hours. >9 mm/s: Initiate shutdown within 1 hour.",
            "5.1": "Maintenance Coordination — All corrective maintenance requires PTW class C (machinery). Hot work requires PTW class B additionally.",
        },
    },
    {
        "id": "DOC-003",
        "name": "OISD Standard 117 — Inspection of Rotary Equipment",
        "type": "regulation",
        "equipment_ids": ["P-101", "P-202", "K-401"],
        "issuing_body": "Oil Industry Safety Directorate (OISD)",
        "sections": {
            "8.3": "Vibration Monitoring — All rotating equipment classified as High Criticality shall have vibration measurements recorded every 4 hours. Equipment operating above alarm setpoint for more than 2 continuous hours must be shut down or a written risk assessment submitted to the safety officer.",
            "9.1": "Inspection Intervals — Class I equipment (High Criticality): Detailed inspection every 6 months, annual overhaul every 3 years.",
            "10.2": "Documentation — All maintenance activities must be logged in CMMS within 24 hours. Incidents must be reported to plant safety officer within 4 hours.",
        },
        "mandatory_requirements": [
            "Vibration monitoring every 4 hours for High Criticality equipment",
            "Shutdown if vibration exceeds alarm for >2 continuous hours (unless risk-assessed)",
            "Annual overhaul documentation required",
        ],
    },
    {
        "id": "DOC-004",
        "name": "P-101 Annual Inspection Report — April 2026",
        "type": "inspection_report",
        "equipment_ids": ["P-101"],
        "date": "2026-04-15",
        "inspector": "Priya Nair",
        "summary": "Overall condition: Satisfactory. Bearing clearance within spec. Seal flush operating normally. Coupling: minor wear — schedule replacement within 90 days. Vibration baseline: 3.5 mm/s (DE), within normal.",
        "open_findings": [
            {"id": "F-001", "description": "Coupling insert showing minor wear", "priority": "Low", "due": "2026-07-15"},
        ],
        "next_inspection": "2026-10-15",
    },
    {
        "id": "DOC-005",
        "name": "ISO 10816-3: Vibration Severity Evaluation — Rotating Machines",
        "type": "standard",
        "equipment_ids": ["P-101", "P-202", "K-401"],
        "sections": {
            "Zone A": "0–2.3 mm/s — New machines (acceptable)",
            "Zone B": "2.3–4.5 mm/s — Normal operating range",
            "Zone C": "4.5–7.1 mm/s — Alarm zone — investigate cause",
            "Zone D": "7.1+ mm/s — Danger zone — risk of damage if operation continues",
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# SPARE PARTS INVENTORY
# ─────────────────────────────────────────────────────────────────────────────

SPARE_PARTS: list[dict[str, Any]] = [
    {
        "id": "SP-001",
        "name": "SKF Bearing 6311 (DE/NDE)",
        "equipment_ids": ["P-101", "P-202"],
        "part_number": "SKF-6311-2RS",
        "quantity_on_hand": 3,
        "reorder_point": 2,
        "lead_time_days": 7,
        "location": "Warehouse A, Rack 4, Bin 12",
        "unit_cost_usd": 280,
        "status": "Available",
    },
    {
        "id": "SP-002",
        "name": "John Crane Type 8B-1 Mechanical Seal",
        "equipment_ids": ["P-101"],
        "part_number": "JC-8B1-55MM",
        "quantity_on_hand": 1,
        "reorder_point": 1,
        "lead_time_days": 14,
        "location": "Warehouse A, Rack 6, Bin 3",
        "unit_cost_usd": 3200,
        "status": "Available",
    },
    {
        "id": "SP-003",
        "name": "Coupling Insert (Flexible Disc)",
        "equipment_ids": ["P-101"],
        "part_number": "RW-RWB-100",
        "quantity_on_hand": 2,
        "reorder_point": 1,
        "lead_time_days": 5,
        "unit_cost_usd": 450,
        "status": "Available",
    },
    {
        "id": "SP-004",
        "name": "SKF LGMT 2 Grease (Cartridge 400g)",
        "equipment_ids": ["P-101", "P-202", "K-401"],
        "part_number": "SKF-LGMT2-0.4",
        "quantity_on_hand": 24,
        "reorder_point": 10,
        "unit_cost_usd": 18,
        "status": "Available",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# TECHNICIANS
# ─────────────────────────────────────────────────────────────────────────────

TECHNICIANS: list[dict[str, Any]] = [
    {
        "id": "TECH-001",
        "name": "Rajesh Kumar",
        "role": "Senior Maintenance Technician",
        "expertise": ["Centrifugal Pumps", "Reciprocating Compressors", "Mechanical Seals"],
        "certifications": ["OSHA 30-Hour", "API 686", "ISO 10816 Vibration Analysis Level II"],
        "years_experience": 18,
        "equipment_ids": ["P-101", "P-202", "K-401"],
        "available": True,
        "contact": "ext. 4512",
    },
    {
        "id": "TECH-002",
        "name": "Amit Shah",
        "role": "Maintenance Technician",
        "expertise": ["Rotating Equipment", "Alignment", "Lubrication"],
        "certifications": ["OSHA 10-Hour", "Vibration Analysis Level I"],
        "years_experience": 9,
        "equipment_ids": ["P-101", "P-202"],
        "available": True,
        "contact": "ext. 4514",
    },
    {
        "id": "TECH-003",
        "name": "Priya Nair",
        "role": "Inspection Engineer",
        "expertise": ["Inspection", "NDT", "Vibration Analysis", "Pressure Vessels"],
        "certifications": ["CSWIP 3.1", "ISO 9712 Level II NDT", "API 510"],
        "years_experience": 12,
        "equipment_ids": ["P-101", "P-202", "HX-201", "V-301"],
        "available": False,
        "current_assignment": "Annual inspection V-301",
        "contact": "ext. 4521",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# COMPLIANCE STATUS
# ─────────────────────────────────────────────────────────────────────────────

COMPLIANCE: dict[str, Any] = {
    "P-101": {
        "overall_score": 85,
        "status": "Warning",
        "issues": [
            {
                "id": "CMP-001",
                "regulation": "OISD-117 Section 8.3",
                "description": "Vibration monitoring interval exceeded — last log entry 6.2 hours ago (required: every 4 hours)",
                "severity": "High",
                "action": "Log vibration reading immediately",
            },
            {
                "id": "CMP-002",
                "regulation": "OISD-117 Section 8.3",
                "description": "Current vibration (7.2 mm/s) exceeds alarm threshold (7.1 mm/s). Shutdown or risk assessment required within 2 hours of alarm.",
                "severity": "High",
                "action": "Initiate shutdown or submit risk assessment within the operating window",
            },
            {
                "id": "CMP-003",
                "regulation": "SOP-P-001 Section 3.1",
                "description": "Lubrication maintenance overdue by 12 days",
                "severity": "Medium",
                "action": "Schedule immediate lubrication as part of corrective maintenance",
            },
        ],
        "passed": [
            "Annual inspection completed (April 2026) — OISD-117 Section 9.1",
            "PTW system active — SOP-P-001 Section 4.1",
            "Spare parts stock above reorder level — SOP Section 7",
        ],
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH STRUCTURE (for visualization)
# ─────────────────────────────────────────────────────────────────────────────

GRAPH_NODES: list[dict[str, Any]] = [
    {"id": "P-101", "name": "Pump P-101\nCrude Feed Pump", "type": "equipment", "val": 28},
    {"id": "P-202", "name": "Pump P-202\nAtm. Residue Pump", "type": "equipment", "val": 20},
    {"id": "HX-201", "name": "HX-201\nFeed Pre-heater", "type": "equipment", "val": 18},
    {"id": "V-301", "name": "V-301\nFeed Surge Drum", "type": "equipment", "val": 18},
    {"id": "K-401", "name": "K-401\nAir Compressor", "type": "equipment", "val": 16},
    {"id": "INC-2022-034", "name": "Bearing Failure\nAug 2022", "type": "incident", "val": 16},
    {"id": "INC-2021-011", "name": "Seal Leakage\nMar 2021", "type": "incident", "val": 12},
    {"id": "INC-2023-067", "name": "Bearing Failure\nNov 2023 (P-202)", "type": "incident", "val": 14},
    {"id": "INC-2020-005", "name": "Impeller Erosion\nJan 2020", "type": "incident", "val": 10},
    {"id": "MR-2026-012", "name": "Lubrication Check\nMay 2026", "type": "maintenance", "val": 10},
    {"id": "MR-OVERDUE", "name": "Lubrication\nOVERDUE 12d", "type": "maintenance_overdue", "val": 14},
    {"id": "DOC-001", "name": "Flowserve\nOEM Manual", "type": "document", "val": 14},
    {"id": "DOC-002", "name": "SOP-P-001\nOperations", "type": "document", "val": 12},
    {"id": "DOC-003", "name": "OISD-117\nInspection Std", "type": "regulation", "val": 16},
    {"id": "DOC-005", "name": "ISO 10816-3\nVibration Std", "type": "regulation", "val": 14},
    {"id": "TECH-001", "name": "Rajesh Kumar\nSr. Technician", "type": "technician", "val": 12},
    {"id": "TECH-002", "name": "Amit Shah\nTechnician", "type": "technician", "val": 10},
    {"id": "TECH-003", "name": "Priya Nair\nInspection Eng.", "type": "technician", "val": 10},
    {"id": "SP-001", "name": "SKF Bearing 6311\n(3 in stock)", "type": "spare_part", "val": 10},
    {"id": "SP-002", "name": "Mech. Seal 8B-1\n(1 in stock)", "type": "spare_part", "val": 10},
    {"id": "COMP-BEARING", "name": "Bearing Assembly\n(Component)", "type": "component", "val": 14},
    {"id": "LOC-CDU", "name": "Unit 4 — CDU", "type": "location", "val": 16},
]

GRAPH_LINKS: list[dict[str, Any]] = [
    {"source": "P-101", "target": "LOC-CDU", "label": "INSTALLED_IN"},
    {"source": "P-202", "target": "LOC-CDU", "label": "INSTALLED_IN"},
    {"source": "HX-201", "target": "LOC-CDU", "label": "INSTALLED_IN"},
    {"source": "V-301", "target": "LOC-CDU", "label": "INSTALLED_IN"},
    {"source": "P-101", "target": "TECH-001", "label": "MAINTAINED_BY"},
    {"source": "P-101", "target": "TECH-002", "label": "MAINTAINED_BY"},
    {"source": "P-101", "target": "TECH-003", "label": "INSPECTED_BY"},
    {"source": "P-101", "target": "INC-2022-034", "label": "EXPERIENCED"},
    {"source": "P-101", "target": "INC-2021-011", "label": "EXPERIENCED"},
    {"source": "P-101", "target": "INC-2020-005", "label": "EXPERIENCED"},
    {"source": "P-202", "target": "INC-2023-067", "label": "EXPERIENCED"},
    {"source": "INC-2022-034", "target": "COMP-BEARING", "label": "ROOT_CAUSE"},
    {"source": "INC-2023-067", "target": "COMP-BEARING", "label": "ROOT_CAUSE"},
    {"source": "INC-2022-034", "target": "INC-2023-067", "label": "SIMILAR_PATTERN"},
    {"source": "P-101", "target": "MR-2026-012", "label": "HAS_MAINTENANCE"},
    {"source": "P-101", "target": "MR-OVERDUE", "label": "HAS_MAINTENANCE"},
    {"source": "P-101", "target": "DOC-001", "label": "DOCUMENTED_IN"},
    {"source": "P-101", "target": "DOC-002", "label": "GOVERNED_BY"},
    {"source": "P-101", "target": "DOC-003", "label": "GOVERNED_BY"},
    {"source": "P-101", "target": "DOC-005", "label": "GOVERNED_BY"},
    {"source": "P-202", "target": "DOC-001", "label": "DOCUMENTED_IN"},
    {"source": "P-101", "target": "SP-001", "label": "REQUIRES_SPARE"},
    {"source": "P-101", "target": "SP-002", "label": "REQUIRES_SPARE"},
    {"source": "COMP-BEARING", "target": "DOC-001", "label": "DESCRIBED_IN"},
    {"source": "COMP-BEARING", "target": "SP-001", "label": "REPLACED_WITH"},
    {"source": "MR-OVERDUE", "target": "TECH-001", "label": "ASSIGNED_TO"},
    {"source": "INC-2022-034", "target": "DOC-001", "label": "REFERENCED_IN"},
    {"source": "P-101", "target": "HX-201", "label": "FEEDS_INTO"},
    {"source": "HX-201", "target": "V-301", "label": "FEEDS_INTO"},
    {"source": "P-101", "target": "P-202", "label": "SIMILAR_TO"},
]

# ─────────────────────────────────────────────────────────────────────────────
# SENSOR HISTORY (last 10 readings for P-101 vibration)
# ─────────────────────────────────────────────────────────────────────────────

SENSOR_HISTORY: dict[str, list[dict[str, Any]]] = {
    "P-101": {
        "vibration_de": [
            {"ts": "2026-07-16T08:00", "value": 3.5},
            {"ts": "2026-07-16T12:00", "value": 3.6},
            {"ts": "2026-07-16T16:00", "value": 3.7},
            {"ts": "2026-07-16T20:00", "value": 3.9},
            {"ts": "2026-07-17T00:00", "value": 4.1},
            {"ts": "2026-07-17T04:00", "value": 4.5},
            {"ts": "2026-07-17T08:00", "value": 5.2},
            {"ts": "2026-07-17T12:00", "value": 5.9},
            {"ts": "2026-07-17T16:00", "value": 6.7},
            {"ts": "2026-07-20T10:00", "value": 7.2},
        ]
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Helper accessors
# ─────────────────────────────────────────────────────────────────────────────

def get_equipment(equipment_id: str) -> dict[str, Any] | None:
    return EQUIPMENT.get(equipment_id) or _DYNAMIC_EQUIPMENT.get(equipment_id)


def get_equipment_incidents(equipment_id: str) -> list[dict[str, Any]]:
    return [i for i in INCIDENTS if i["equipment_id"] == equipment_id]


def get_maintenance_records(equipment_id: str) -> list[dict[str, Any]]:
    return [m for m in MAINTENANCE_RECORDS if m["equipment_id"] == equipment_id]


def get_equipment_documents(equipment_id: str) -> list[dict[str, Any]]:
    return [d for d in DOCUMENTS if equipment_id in d.get("equipment_ids", [])]


def get_equipment_spare_parts(equipment_id: str) -> list[dict[str, Any]]:
    return [s for s in SPARE_PARTS if equipment_id in s.get("equipment_ids", [])]


def get_equipment_technicians(equipment_id: str) -> list[dict[str, Any]]:
    eq = EQUIPMENT.get(equipment_id, {})
    names = eq.get("technicians", [])
    return [t for t in TECHNICIANS if t["name"] in names]


def find_similar_incidents(query_keywords: list[str], exclude_equipment_id: str | None = None) -> list[dict[str, Any]]:
    """Find incidents whose keywords overlap with the query keywords."""
    scored: list[tuple[int, dict[str, Any]]] = []
    for incident in INCIDENTS:
        if exclude_equipment_id and incident["equipment_id"] == exclude_equipment_id:
            score = sum(1 for kw in query_keywords if kw.lower() in str(incident.get("keywords", [])).lower())
        else:
            score = sum(1 for kw in query_keywords if kw.lower() in str(incident.get("keywords", [])).lower())
        if score > 0:
            scored.append((score, incident))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:3]]


def get_all_equipment_list() -> list[dict[str, Any]]:
    return list(EQUIPMENT.values()) + list(_DYNAMIC_EQUIPMENT.values())


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC EQUIPMENT REGISTRY  (populated at runtime from document uploads)
# ─────────────────────────────────────────────────────────────────────────────

_DYNAMIC_EQUIPMENT: dict[str, dict[str, Any]] = {}

# Tags that indicate instruments (not equipment — skip auto-registration)
_INSTRUMENT_PREFIXES = {"FT", "PT", "TT", "LT", "VT", "AT", "XT", "ZT", "ST",
                        "FIC", "PIC", "TIC", "LIC", "FCV", "PCV", "TCV",
                        "DPDP", "AHU", "PSV", "PRV"}

# Equipment type inference from ISA/ISA-5.1 tag prefix patterns
_TYPE_MAP = [
    (("P",),               "Centrifugal Pump"),
    (("K", "C"),           "Compressor"),
    (("HX", "E"),          "Heat Exchanger"),
    (("V", "DR"),          "Pressure Vessel"),
    (("T",),               "Storage Tank"),
    (("MOV", "FV", "HV"),  "Valve"),
    (("B",),               "Blower"),
    (("F",),               "Filter / Furnace"),
    (("R",),               "Reactor"),
    (("G",),               "Generator"),
    (("M",),               "Motor"),
]


def _infer_type(equipment_id: str) -> str:
    prefix = equipment_id.split("-")[0].upper()
    for prefixes, eq_type in _TYPE_MAP:
        if prefix in prefixes:
            return eq_type
    return "Unknown Equipment"


def _is_instrument(equipment_id: str) -> bool:
    prefix = equipment_id.split("-")[0].upper()
    return prefix in _INSTRUMENT_PREFIXES


def register_equipment(
    equipment_id: str,
    source_document: str,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Auto-register a new equipment ID discovered from a document.
    Returns None if the tag is already known or is an instrument tag.
    """
    if equipment_id in EQUIPMENT:
        return None                         # already in static registry
    if equipment_id in _DYNAMIC_EQUIPMENT:
        # Merge additional source documents
        existing = _DYNAMIC_EQUIPMENT[equipment_id]
        src = existing.get("_source_documents", [])
        if source_document not in src:
            src.append(source_document)
        return existing
    if _is_instrument(equipment_id):
        return None                         # skip instruments

    record: dict[str, Any] = {
        "id": equipment_id,
        "name": f"{equipment_id} ({_infer_type(equipment_id)})",
        "type": _infer_type(equipment_id),
        "location": "Pending — see source document",
        "health_score": None,
        "failure_probability": None,
        "compliance_score": None,
        "maintenance_due_days": None,
        "criticality": "Unknown",
        "status": "Discovered",
        # Discovery metadata
        "_discovered": True,
        "_source_documents": [source_document],
        "_discovered_at": datetime.now().isoformat(),
    }
    if extra_context:
        record.update(extra_context)

    _DYNAMIC_EQUIPMENT[equipment_id] = record
    return record


def get_discovered_equipment() -> list[dict[str, Any]]:
    return list(_DYNAMIC_EQUIPMENT.values())
