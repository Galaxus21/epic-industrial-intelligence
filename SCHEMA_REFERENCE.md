# OpsBrain — Database Schema, Relationships & Sample Usage Guide
_Generated 2026-07-22 · PostgreSQL (SQLAlchemy ORM) · 24 tables_

---

## 1. Entity Hierarchy

```
PROJECT (projects)
  └─ PLANT (plants)           plant_id → project.id
       ├─ EQUIPMENT (equipment)           plant stores equipment_ids[]
       │    ├─ SENSOR_HISTORY             equipment_id FK
       │    ├─ MAINTENANCE_RECORD         equipment_id FK
       │    ├─ INCIDENT (legacy)          equipment_id FK
       │    ├─ COMPLIANCE                 equipment_id PK (1-to-1)
       │    ├─ SPARE_PART                 equipment_ids[] JSON
       │    └─ TECHNICIAN                 equipment_ids[] JSON
       │
       ├─ DRAWING (drawings)              plant_id + project_id FK
       │
       ├─ PERMIT_TO_WORK (permits_to_work)   plant_id + project_id FK
       │    └─ → MANAGED_WORK_ORDER via permit_id
       │
       ├─ SAFETY_PROCEDURE (safety_procedures)  plant_id + project_id FK
       │
       ├─ MANAGED_WORK_ORDER (managed_work_orders)  plant_id + project_id FK
       │    └─ → PERMIT_TO_WORK via permit_id (optional)
       │
       ├─ INCIDENT_REPORT (incident_reports)   plant_id + project_id FK
       │    └─ CAPA_ITEMS (embedded JSON)
       │
       ├─ QUALITY_INSPECTION (quality_inspections)  plant_id + project_id FK
       │    └─ NON_CONFORMANCES (embedded JSON)
       │
       └─ ACTION_ITEM (action_items)      plant_id FK, source_id → any entity

USER_PROFILE (user_profiles)
  └─ plant_ids[] (which plants the user covers)
  └─ role drives approval workflows across PTW, WO, Procedures

KNOWLEDGE GRAPH (graph_nodes + graph_links)
  └─ mirrors all entities as nodes with typed relationship edges

DOCUMENT_RECORD (documents)
  └─ equipment_ids[] (spans multiple equipment)

SAVED_CHECKLIST (saved_checklists)   — AI-generated, per equipment
SAVED_WORK_ORDER (saved_work_orders) — AI-generated, per equipment
AUDIT_LOG (audit_logs)               — immutable trail for every change
```

---

## 2. Table-by-Table Reference

### 2.1 Project
**Table:** `projects` | **API:** `POST/GET /api/v1/pm/projects`

| Field | Type | Notes |
|---|---|---|
| id | PK string | `PROJ-XXXXXXXX` |
| code | unique string | `PRJ-001` |
| name | string | Human name |
| type | enum | `Industrial` \| `Shutdown` \| `Turnaround` |
| phase | enum | `Planning` \| `Execution` \| `Operations` \| `Closed` |
| status | enum | `Active` \| `On-Hold` \| `Closed` |
| plant_ids | JSON `[]` | Child plant IDs |
| equipment_ids | JSON `[]` | Direct equipment IDs |
| manager_id | string → user_profiles.id | Project manager |

**Relationships:**
- One project → many plants (`Plant.project_id`)
- One project → many drawings (`Drawing.project_id`)
- One project → many PTWs, WOs, Incidents, Inspections, Procedures (all have `project_id`)

---

### 2.2 Plant
**Table:** `plants` | **API:** `POST/GET /api/v1/pm/plants`

| Field | Type | Notes |
|---|---|---|
| id | PK string | `PLANT-XXXXXXXX` |
| code | string | `CDU-01` |
| project_id | FK → projects.id (indexed) | Parent project |
| type | enum | `Process Unit` \| `Storage` \| `Utility` … |
| status | enum | `Operational` \| `Shutdown` \| `Mothballed` |
| equipment_ids | JSON `[]` | Equipment at this plant |
| responsible_person_id | FK → user_profiles.id | Plant custodian |

**Relationships:**
- Many plants per project
- Equipment at this plant linked via `equipment_ids[]`
- PTW, WO, Drawing, Inspection all FK to `plant_id`

---

### 2.3 Equipment
**Table:** `equipment` | **API:** `GET /api/v1/equipment/{id}`

| Field | Type | Notes |
|---|---|---|
| id | PK string | e.g. `P-101` |
| type | string | `Centrifugal Pump` \| `Compressor` … |
| health_score | float 0–100 | Computed by AI |
| failure_probability | float 0–100 | Computed by AI |
| compliance_score | float 0–100 | From Compliance table |
| maintenance_due_days | int | Negative = overdue |
| current_readings | JSON `{key: {value, unit, alarm, trip}}` | Live sensor values |
| downstream_equipment | JSON `[id,…]` | Flow/process chain |
| discovered | bool | Auto-discovered from document upload |
| source_documents | JSON `[name,…]` | Which uploads mentioned this equipment |

**Relationships:**
- `equipment_id` FK in: `incidents`, `maintenance_records`, `saved_checklists`, `saved_work_orders`, `sensor_history`, `compliance`
- `equipment_ids[]` JSON in: `managed_work_orders`, `incident_reports`, `quality_inspections`, `permits_to_work`, `safety_procedures`, `spare_parts`
- Knowledge graph: equipment appears as a node; linked to incidents, documents, WOs, technicians via `graph_links`

---

### 2.4 Incident (Legacy — AI/system-generated)
**Table:** `incidents` | **API:** via `db_service` only (no direct REST endpoint)

| Field | Type | Notes |
|---|---|---|
| id | PK string | `INC-XXXX` · `LESSON-XXXX` · `PTW-XXXX` |
| equipment_id | FK string (indexed) | Which equipment |
| severity | enum | `Critical` \| `High` \| `Medium` \| `Low` |
| root_cause_category | string | `Mechanical` \| `Process` \| `Maintenance` … |
| downtime_hours | int | Operational impact |
| cost_usd | float | Financial impact |
| keywords | JSON `[]` | For similarity search |

**ID prefix convention:**
- `INC-*` — real equipment incident
- `LESSON-*` — lessons learned from a completed work order
- `PTW-*` — safety conflict check result (from `/api/v1/safety/check-conflict`)

**Important:** This is the *legacy / AI-generated* table. User-facing incidents go to `incident_reports`. Both tables are queried together by the reports API.

---

### 2.5 IncidentReport (Workflow — user-reported)
**Table:** `incident_reports` | **API:** `POST/GET /api/v1/incidents`

| Field | Type | Notes |
|---|---|---|
| id | PK string | `IR-XXXXXXXX` |
| incident_number | unique string | `INC-2026-0001` |
| incident_type | enum | `near_miss` \| `first_aid` \| `medical_treatment` \| `lost_time` \| `fatality` \| `environmental` \| `property_damage` \| `fire` \| `spill` |
| severity | enum P1–P5 | P1=Fatality, P2=Lost Time, P3=Medical, P4=First Aid, P5=Near Miss |
| status | enum | `reported` → `investigation` → `root_cause_analysis` → `capa` → `closed` |
| equipment_ids | JSON `[]` | Affected equipment |
| project_id / plant_id | FK strings | Context |
| persons_involved | JSON `[{name, role, injury}]` | HSE requirement |
| root_causes | JSON `[{level, cause, category}]` | 5-Why / Bow-Tie |
| capa_items | JSON `[{id, type, description, due_date, status}]` | CAPA tracking |
| downtime_hours | float | *(Added recently; live from reports)* |
| cost_usd | float | *(Added recently; live from reports)* |
| root_cause_category | string | *(Added recently)* |

**Workflow states:**
```
reported → investigation → root_cause_analysis → capa → closed
```

---

### 2.6 MaintenanceRecord
**Table:** `maintenance_records` | **Written by:** forms API, kb_ingestion, threshold monitor

| Field | Type | Notes |
|---|---|---|
| id | PK string | `MR-XXXX` \| `MR-DONE-XXXX` \| `MR-CL-XXXX` |
| equipment_id | FK string (indexed) | Which equipment |
| type | string | `Preventive` \| `Corrective` \| `Inspection` \| `Sensor Log` |
| status | enum | `Completed` \| `Scheduled` \| `Overdue` |
| technician | string | Name (from UserProfile or forms) |

---

### 2.7 QualityInspection
**Table:** `quality_inspections` | **API:** `POST/GET /api/v1/inspections`

| Field | Type | Notes |
|---|---|---|
| id | PK string | `QI-XXXXXXXX` |
| inspection_number | unique | `QI-2026-001` |
| inspection_type | enum | `equipment` \| `process` \| `safety_audit` \| `environmental` \| `contractor` \| `pre_startup` |
| status | enum | `scheduled` → `in_progress` → `pending_review` → `closed_satisfactory` \| `closed_with_findings` \| `rejected` |
| checklist_items | JSON `[{seq, check_item, criteria, result, findings}]` | Pass/Fail per item |
| non_conformances | JSON `[{id, description, severity, action_required, due_date}]` | Defects found |
| overall_score | float | % of checklist items passed |
| equipment_ids | JSON `[]` | Which equipment inspected |

**Note:** Defects are recorded here as `non_conformances`. They can also be submitted via the Forms Hub → Defect Report (which writes to both `incidents` legacy table AND `incident_reports` with `incident_type=property_damage`).

---

### 2.8 PermitToWork (PTW)
**Table:** `permits_to_work` | **API:** `POST/GET /api/v1/permits`

| Field | Type | Notes |
|---|---|---|
| id | PK string | `PTW-XXXXXXXX` |
| permit_number | unique | `PTW-2026-001` |
| permit_type | enum | `hot_work` \| `cold_work` \| `confined_space` \| `electrical_isolation` \| `height` \| `radiography` \| `excavation` |
| status | enum | See 10-stage workflow below |
| equipment_ids | JSON `[]` | Equipment being worked on |
| work_order_id | FK → managed_work_orders.id | Optional linked WO |
| hazards | JSON `[{hazard, likelihood, severity, mitigation}]` | JSA |
| isolation_points | JSON `[{tag_number, isolation_type, verified_by}]` | LOTO |
| gas_tests | JSON `[{tested_by, gas, ppm, lel_percent}]` | Confined space |
| ppe_requirements | JSON `[{item, specification}]` | Required PPE |
| originator_* | string fields | Person requesting |
| area_authority_* | string fields + decision | Equipment owner approval |
| safety_officer_* | string fields + decision | Safety validation |
| ap_* | string fields + decision | Authorized Person issues/closes |
| audit_trail | JSON `[]` | Full history of every status change |

**10-stage workflow:**
```
draft → submitted → area_authority_review → safety_review → ap_approval
→ issued → active → suspended → completion_requested → closed | cancelled
```

---

### 2.9 SafetyProcedure
**Table:** `safety_procedures` | **API:** `POST/GET /api/v1/procedures`

| Field | Type | Notes |
|---|---|---|
| id | PK string | `SP-XXXXXXXX` |
| code | string | `SOP-PUMP-001` |
| doc_type | enum | `SOP` \| `JSA` \| `SWMS` \| `MSDS` \| `ERP` \| `Checklist` \| `Work_Instruction` |
| version | string | `1.0`, `2.1` … |
| status | enum | See 6-stage workflow below |
| steps | JSON `[{step_number, title, description, hazards, controls, responsible_role}]` | Procedure body |
| hazard_register | JSON `[{hazard, risk_before, risk_after, control_measure}]` | JSA risk register |
| equipment_ids | JSON `[]` | Governing which equipment |
| author_* / peer_reviewer_* / tech_reviewer_* / approver_* | string fields + decisions | 4-party review chain |

**6-stage workflow:**
```
draft → peer_review → technical_review → final_approval → active → obsolete
```

---

### 2.10 ManagedWorkOrder
**Table:** `managed_work_orders` | **API:** `POST/GET /api/v1/work-orders`

| Field | Type | Notes |
|---|---|---|
| id | PK string | `MWO-XXXXXXXX` |
| wo_number | unique | `WO-2026-001` |
| category | enum | `preventive` \| `corrective` \| `predictive` \| `emergency` \| `shutdown` \| `modification` |
| priority | enum | `low` \| `medium` \| `high` \| `critical` |
| status | enum | See 8-stage workflow below |
| equipment_ids | JSON `[]` | Equipment being maintained |
| permit_id | FK → permits_to_work.id | Linked PTW (optional) |
| tasks | JSON `[{seq, title, trade, estimated_hours, status}]` | Work breakdown |
| materials | JSON `[{part_number, description, qty_required, qty_issued}]` | Parts used |
| assigned_to | JSON `[{id, name, role}]` | Assigned technicians |
| created_by_* / approver_* / started_by_* / completed_by_* / verified_by_* | string fields | **Two-person rule** — creator ≠ approver; completer ≠ verifier |

**8-stage workflow with two-person rule:**
```
draft → submitted → pending_approval → approved → scheduled
→ in_progress → pending_verification → verified → closed
```
- `HTTP 403` if creator == approver
- `HTTP 403` if completer == verifier

---

### 2.11 SavedChecklist (AI-generated)
**Table:** `saved_checklists` | **API:** `POST/GET /api/v1/ops/checklists`

AI generates inspection checklists from natural language queries. This is the *quick capture* path; `QualityInspection` is the formal workflow.

| Field | Type | Notes |
|---|---|---|
| equipment_id | FK string | Which equipment |
| query_text | text | Original AI query |
| risk_level | string | `High` \| `Medium` \| `Low` |
| items | JSON `[{text, checked, notes}]` | Checklist items |
| status | enum | `open` \| `in_progress` \| `completed` |

---

### 2.12 SavedWorkOrder (AI-generated)
**Table:** `saved_work_orders` | **API:** `POST/GET /api/v1/ops/work-orders`

AI generates work orders from natural language queries. Forms API also writes here for quick capture; `ManagedWorkOrder` is the formal approval-chain path.

| Field | Type | Notes |
|---|---|---|
| equipment_id | FK string | Which equipment |
| wo_type | string | `Corrective` \| `Preventive` \| `Emergency` |
| steps | JSON `[{step, phase, title, safety_note, expected_duration_minutes, checked, actual_notes}]` | Step-by-step execution |
| solution_worked | bool | Post-completion feedback |
| spare_parts | JSON `[]` | Parts required |
| required_permits | JSON `[]` | PTW class needed |

---

### 2.13 ActionItem (CAPA)
**Table:** `action_items` | **API:** `POST/GET /api/v1/inspections/actions`

| Field | Type | Notes |
|---|---|---|
| source_type | enum | `incident` \| `inspection` \| `audit` \| `observation` |
| source_id | string | FK to the source entity |
| action_type | enum | `corrective` \| `preventive` \| `improvement` \| `observation` |
| status | enum | `open` → `in_progress` → `pending_verification` → `verified` \| `overdue` |
| assigned_to_* / completed_by_* / verifier_* | string fields | Three-party accountability |

---

### 2.14 SparePart
**Table:** `spare_parts` | **API:** `GET/POST/PATCH/DELETE /api/v1/spare-parts`

| Field | Type | Notes |
|---|---|---|
| equipment_ids | JSON `[]` | Equipment this part supports |
| quantity_on_hand | int | Current stock |
| reorder_point | int | Triggers "Low Stock" status |
| status | auto-computed | `Available` \| `Low Stock` \| `Out of Stock` \| `Discontinued` |
| unit_cost_usd | float | For cost calculations |

**Stock issue endpoint:** `POST /api/v1/spare-parts/{id}/issue` decrements quantity.

---

### 2.15 UserProfile
**Table:** `user_profiles` | **API:** `GET/POST /api/v1/users`

| Field | Type | Notes |
|---|---|---|
| employee_id | unique string | HR identifier |
| role | enum | `technician` \| `supervisor` \| `safety_officer` \| `area_authority` \| `authorized_person` \| `manager` \| `quality_inspector` |
| plant_ids | JSON `[]` | Which plants this user covers |
| certifications | JSON `[]` | e.g. `["HAZOP", "First Aid", "PTW-AP"]` |

**Role determines approval capabilities:**
- `area_authority` → approves PTW at area_authority_review stage
- `safety_officer` → approves PTW at safety_review stage
- `authorized_person` → issues/closes PTW
- `supervisor` → approves ManagedWorkOrder
- `quality_inspector` → verifies ManagedWorkOrder

---

### 2.16 DocumentRecord
**Table:** `documents` | **API:** `POST /api/v1/documents/upload`

| Field | Type | Notes |
|---|---|---|
| equipment_ids | JSON `[]` | Which equipment this document mentions |
| type | string | `sop` \| `manual` \| `incident_report` \| `inspection_report` \| `drawing` \| `work_order` … |
| sections | JSON `{section_id: text}` | Extracted text chunks |
| entities | JSON `{equipment_ids, people, regulations, …}` | LLM-extracted entities |
| pipeline_steps | JSON `{step: done\|pending}` | 6-step processing pipeline |

**16 supported file formats:** PDF, DOCX, TXT, CSV, XLSX, PNG, JPG, TIFF, DXF, DWG, STEP, IGES, IFC, DGN, SVG, BMP

---

### 2.17 Drawing
**Table:** `drawings` | **API:** `POST /api/v1/drawings/upload`

| Field | Type | Notes |
|---|---|---|
| project_id / plant_id | FK strings | Hierarchy |
| drawing_type | enum | `pid` \| `pfd` \| `electrical` \| `mechanical` \| `isometric` \| `layout` |
| extracted_svg_path | string | Dark-theme SVG for the viewer |
| extracted_data | JSON `{equipment:[], instruments:[], connections:[]}` | P&ID entities |
| analytics | JSON `{incident_count, active_ptw_count, open_wo_count}` | Live from DB |

---

### 2.18 Compliance
**Table:** `compliance` (1-to-1 with Equipment) | **API:** `GET/POST/PATCH /api/v1/compliance/{id}`

| Field | Type | Notes |
|---|---|---|
| equipment_id | PK FK → equipment.id | One record per equipment |
| overall_score | int 0–100 | Severity-weighted: Critical=-20, High=-10, Medium=-5, Low=-2 |
| issues | JSON `[{id, item, severity, standard}]` | Open compliance gaps |
| passed | JSON `[{item, resolved_by, resolved_at}]` | Resolved items |

---

### 2.19 Knowledge Graph
**Tables:** `graph_nodes` + `graph_links`

| GraphNode field | Notes |
|---|---|
| id | Mirrors the entity's own id |
| type | `equipment` \| `incident` \| `work_order` \| `document` \| `plant` \| `project` \| `defect` \| `inspection` \| `safety_procedure` |
| val | Visual size weight |

**Relationship labels in `graph_links.label`:**
```
HAS_INCIDENT         equipment → incident
HAS_WORK_ORDER       equipment → work_order
DOCUMENTED_IN        equipment → document
EXPERIENCED          equipment → incident (Neo4j)
GOVERNED_BY          equipment → compliance/regulation
BELONGS_TO           plant → project
LOCATED_IN           equipment → plant
INVOLVES             incident → equipment
APPLIES_TO           work_order → equipment
COVERS               inspection → equipment
GOVERNS              safety_procedure → equipment
DEFECT_ON            defect → equipment
REFERENCES           document → incident/WO/inspection/SOP/project/plant
SIMILAR_PATTERN      incident → incident (cross-equipment learning)
ROOT_CAUSE           incident → component (Neo4j)
```

---

### 2.20 SensorHistory
**Table:** `sensor_history`

```
{equipment_id, sensor_key, readings: [{ts, value, unit, raw}]}
```

Appended by:
- Smart Forms → Sensor Log submission
- Smart Forms → Maintenance Record (sensor fields)
- Threshold monitor (autonomous, every 60s)

---

### 2.21 AuditLog
**Table:** `audit_logs` — **immutable**, ISO 27001 compliant

Every create/update/complete/delete on any operational object triggers an entry.
`object_type` values: `work_order` · `checklist` · `incident` · `equipment` · `sensor` · `safety` · `defect` · `document` · `spare_part` · `compliance` · `permit` · `inspection` · `procedure`

---

## 3. Cross-Entity Relationships Map

```
UserProfile ──(role)──────────────────────────────────────────────────────────┐
     │                                                                         │
Project ──(plant_ids[])──► Plant ──(equipment_ids[])──► Equipment             │
     │                        │                              │                 │
     │         ┌──────────────┼──────────────────────────── │ ─────────┐      │
     │         ▼              ▼                              ▼          ▼      │
     │      Drawing     SafetyProcedure            Compliance     SparePart    │
     │         │         (equipment_ids[])          (1-to-1)   (equipment_ids[])
     │         │                                       │                       │
     ▼         ▼                                       │                       │
PermitToWork ──(work_order_id)──► ManagedWorkOrder     │                       │
     │                   │                             │                       │
     │                   │ (equipment_ids[])           │                       │
     │                   │                             │                       │
     ▼                   ▼                             ▼                       │
IncidentReport    QualityInspection           MaintenanceRecord                │
     │                   │                          │                          │
     ▼                   ▼                          ▼                          │
 ActionItem ◄──────────(source_id)──────────────────┘                          │
                                                                               │
All workflow tables ──(created_by_name / approver_name)──────────────────────►┘
                    reference UserProfile by name string (not FK)
```

> **Note on FK style:** Relationships are implemented as JSON arrays (`equipment_ids[]`, `plant_ids[]`) or string fields (`project_id`, `plant_id`, `equipment_id`) rather than SQLAlchemy `relationship()` with FK constraints. This keeps schema flexible for the hackathon prototype while still allowing cross-entity queries.

---

## 4. Sample REST API Usage

### Scenario: "Bearing failure on P-101 — full lifecycle from alert to closure"

---

#### Step 1 — Register equipment (if new)
```http
POST /api/v1/forms/submit
{
  "form_type": "equipment_reg",
  "field_values": {
    "id": "P-101",
    "name": "Crude Oil Feed Pump",
    "type": "Centrifugal Pump",
    "location": "Unit 4 — CDU",
    "criticality": "Critical",
    "manufacturer": "Flowserve",
    "model": "PVXM-100"
  }
}
→ 201 { "id": "P-101", "message": "Equipment registered" }
```

---

#### Step 2 — Log vibration reading
```http
POST /api/v1/forms/submit
{
  "form_type": "sensor_log",
  "equipment_id": "P-101",
  "field_values": {
    "date": "2026-07-22",
    "vibration_de": "7.4",
    "technician": "Rajesh Kumar"
  }
}
→ 200 { "updated_sensors": ["vibration_de"], "message": "Sensor log saved" }
```

---

#### Step 3 — AI query: can I continue operating?
```http
POST /api/v1/agents/query          (SSE stream)
{
  "equipment_id": "P-101",
  "query": "Vibration has reached 7.4 mm/s. Can I continue operating?"
}
→ Stream: equipment_brain → maintenance_advisor → compliance_agent → lessons_learned → synthesizer
→ Final: { "risk_level": "High", "probable_causes": [...], "work_order": {...} }
```

---

#### Step 4 — Report the incident formally
```http
POST /api/v1/incidents
{
  "title": "P-101 vibration alarm — potential bearing failure",
  "incident_type": "near_miss",
  "severity": "P3",
  "equipment_ids": ["P-101"],
  "description": "Vibration on DE side reached 7.4 mm/s exceeding 7.1 alarm.",
  "occurred_at": "2026-07-22T14:30:00",
  "reported_by_name": "Rajesh Kumar",
  "immediate_actions": ["Reduced pump speed to 85% BEP"],
  "downtime_hours": 0.0
}
→ 201 { "id": "IR-ABCD1234", "incident_number": "INC-2026-0042", "status": "reported" }
```

---

#### Step 5 — Create a Permit to Work
```http
POST /api/v1/permits
{
  "permit_number": "PTW-2026-042",
  "permit_type": "cold_work",
  "title": "Replace DE bearing on P-101",
  "scope_of_work": "Remove and replace drive-end bearing. Isolate suction MOV-101A.",
  "plant_id": "PLANT-CDU01",
  "equipment_ids": ["P-101"],
  "hazards": [{ "hazard": "Rotating machinery", "likelihood": "Medium", "severity": "High", "mitigation": "LOTO applied" }],
  "isolation_points": [{ "tag_number": "MOV-101A", "isolation_type": "valve_closed", "verified_by": "Rajesh Kumar" }],
  "ppe_requirements": [{ "item": "Safety glasses" }, { "item": "Safety boots" }],
  "originator_name": "Rajesh Kumar",
  "originator_date": "2026-07-22"
}
→ 201 { "id": "PTW-ABCD1234", "status": "draft" }
```

#### Submit PTW for review
```http
POST /api/v1/permits/PTW-ABCD1234/submit
{ "submitted_by_id": "USR-001", "submitted_by_name": "Rajesh Kumar" }
→ 200 { "status": "submitted" }
```

#### Area Authority approves
```http
POST /api/v1/permits/PTW-ABCD1234/area-authority
{ "decision": "approved", "decision_by_id": "USR-002",
  "decision_by_name": "Suresh Patel", "comments": "Isolation verified" }
→ 200 { "status": "area_authority_review" }  → continues workflow
```

---

#### Step 6 — Create a Managed Work Order (linked to PTW)
```http
POST /api/v1/work-orders
{
  "wo_number": "WO-2026-042",
  "title": "P-101 DE bearing replacement",
  "category": "corrective",
  "priority": "high",
  "equipment_ids": ["P-101"],
  "permit_id": "PTW-ABCD1234",
  "estimated_hours": 4.0,
  "tasks": [
    { "seq": 1, "title": "Isolate pump", "trade": "mechanical", "estimated_hours": 0.5 },
    { "seq": 2, "title": "Remove bearing housing", "trade": "mechanical", "estimated_hours": 1.0 },
    { "seq": 3, "title": "Replace SKF 6311 bearing", "trade": "mechanical", "estimated_hours": 1.5 },
    { "seq": 4, "title": "Reassemble and alignment check", "trade": "mechanical", "estimated_hours": 1.0 }
  ],
  "materials": [{ "part_number": "SKF-6311", "description": "Deep groove ball bearing", "qty_required": 1 }],
  "created_by_name": "Rajesh Kumar"
}
→ 201 { "id": "MWO-ABCD1234", "wo_number": "WO-2026-042", "status": "draft" }
```

#### Issue a spare part
```http
POST /api/v1/spare-parts/SP-001/issue
{ "quantity": 1, "issued_to": "Rajesh Kumar", "work_order_id": "MWO-ABCD1234" }
→ 200 { "quantity_remaining": 2, "status": "Low Stock" }
```

---

#### Step 7 — Schedule a Quality Inspection (pre-maintenance)
```http
POST /api/v1/inspections
{
  "inspection_number": "QI-2026-042",
  "title": "Pre-maintenance bearing inspection — P-101",
  "inspection_type": "equipment",
  "equipment_ids": ["P-101"],
  "scheduled_date": "2026-07-22",
  "checklist_items": [
    { "seq": 1, "check_item": "Bearing condition", "criteria": "No spalling or pitting" },
    { "seq": 2, "check_item": "Shaft runout", "criteria": "< 0.05 mm" },
    { "seq": 3, "check_item": "Seal integrity", "criteria": "No leakage" }
  ]
}
→ 201 { "id": "QI-ABCD1234", "inspection_number": "QI-2026-042", "status": "scheduled" }
```

#### Close inspection with findings
```http
PATCH /api/v1/inspections/QI-ABCD1234/review
{
  "reviewer_id": "USR-003",
  "reviewer_name": "Priya Nair",
  "reviewer_decision": "closed_with_findings",
  "reviewer_comments": "Bearing spalling confirmed on DE side"
}
```

---

#### Step 8 — Add CAPA from inspection finding
```http
POST /api/v1/inspections/actions
{
  "title": "Lubrication interval reduction — P-101",
  "description": "Reduce grease interval from 30 to 14 days following bearing failure",
  "source_type": "inspection",
  "source_id": "QI-ABCD1234",
  "action_type": "preventive",
  "priority": "high",
  "assigned_to_name": "Maintenance Supervisor",
  "due_date": "2026-08-05"
}
→ 201 { "id": "ACT-ABCD1234", "action_number": "ACT-2026-001", "status": "open" }
```

---

#### Step 9 — Upload maintenance SOP
```http
POST /api/v1/procedures
{
  "code": "SOP-P101-BEARING",
  "title": "P-101 Bearing Replacement Procedure",
  "doc_type": "SOP",
  "category": "Mechanical",
  "equipment_ids": ["P-101"],
  "risk_level": "High",
  "steps": [
    { "step_number": 1, "title": "Isolate energy", "description": "Apply LOTO per PTW", "responsible_role": "technician" },
    { "step_number": 2, "title": "Remove bearing", "description": "Use bearing puller…" }
  ],
  "author_name": "Priya Nair"
}
→ 201 { "status": "draft" }

POST /api/v1/procedures/{id}/peer-review
{ "decision": "approved", "reviewer_name": "Suresh Patel" }

POST /api/v1/procedures/{id}/technical-review
{ "decision": "approved", "reviewer_name": "Dr. Anand" }

POST /api/v1/procedures/{id}/approve
{ "decision": "approved", "approver_name": "HSE Manager" }
→ status = "active"
```

---

#### Step 10 — Close out incident investigation
```http
POST /api/v1/incidents/IR-ABCD1234/root-cause
{
  "root_causes": [
    { "level": 1, "cause": "Lubrication interval exceeded by 12 days", "category": "Maintenance" },
    { "level": 2, "cause": "Maintenance schedule not linked to digital system", "category": "Process" }
  ],
  "contributing_factors": ["Manual maintenance tracking", "No automated reminder"]
}

POST /api/v1/incidents/IR-ABCD1234/capa/add
{ "action_type": "corrective", "description": "Replace bearing with upgraded SKF model",
  "assigned_to_name": "Rajesh Kumar", "due_date": "2026-07-25" }

POST /api/v1/incidents/IR-ABCD1234/close
{ "closed_by_name": "HSE Manager", "closure_comments": "Bearing replaced, SOP updated, CAPA verified" }
→ status = "closed"
```

---

## 5. Forms Hub Quick-Capture Reference

| Form Type | DB Tables Written | API Endpoint |
|---|---|---|
| Maintenance Record | `maintenance_records` + `sensor_history` (if sensor fields) | `POST /api/v1/forms/submit` |
| Sensor Log | `maintenance_records` + `sensor_history` + `equipment.current_readings` | same |
| Incident Report | `incidents` (legacy) + `incident_reports` (workflow) | same |
| Work Order | `saved_work_orders` (AI) + `managed_work_orders` (workflow) | same |
| Defect Report | `incidents` (legacy) + `incident_reports` (type=property_damage) | same |
| Equipment Registration | `equipment` + `graph_nodes` | same |

**Generate form from natural language:**
```http
POST /api/v1/forms/generate
{ "description": "log a vibration check for P-101", "equipment_id": "P-101" }
→ { "form_id": "FORM-ABC", "fields": [...], "submit_action": "maintenance_record" }
```

---

## 6. Compliance Write API (live, not seed-only)

```http
# Update compliance record
POST /api/v1/compliance/P-101
{ "overall_score": 78, "issues": [{"item": "OISD-117 Sec 8.3 violation", "severity": "High"}] }

# Resolve one issue
POST /api/v1/compliance/P-101/resolve-issue
{ "item": "OISD-117 Sec 8.3 violation", "resolved_by": "HSE Manager",
  "resolution_note": "Alarm response SOP updated and re-trained" }
→ { "new_score": 88, "new_status": "Warning", "open_issues": 1 }
```

---

## 7. Knowledge Graph & Vector Search

### Graph API
```http
GET  /api/v1/knowledge-graph              # all nodes + links
GET  /api/v1/knowledge-graph/status       # { neo4j_active, qdrant_active }
GET  /api/v1/knowledge-graph/P-101/traverse?depth=2   # Neo4j Cypher multi-hop
GET  /api/v1/knowledge-graph/P-101/similar            # equipment with similar failures
```

### Document upload → auto-indexed into Qdrant
```http
POST /api/v1/documents/upload   (multipart/form-data: file + equipment_id)
→ Pipeline: saved → extracted → entities → drawing → graph → indexed(Qdrant)
→ Agent queries now use semantic search across all uploaded docs
```

---

## 8. Admin & Demo

```http
POST /api/v1/admin/seed-demo
→ Creates: P-101-DEMO equipment + vibration alarm + incident report + WO + PTW + inspection
→ Returns: { "message": "navigate to /query, select P-101-DEMO, ask: 'Pump vibration increased...'" }

GET  /api/v1/admin/stats         # record counts per entity type
DELETE /api/v1/admin/purge?entity=all   # wipe all data (permanent)
```

---

*Tables: 24 · API routers: 25 · Workflow entities: 8 · Supported file formats: 16*
