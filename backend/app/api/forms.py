"""
AI Operations Brain — Smart Forms API
Describe what you want to record in plain language; the LLM generates
a structured form schema with the right fields pre-populated from equipment specs.

Endpoints:
  POST /api/v1/forms/generate         — description → form schema JSON
  POST /api/v1/forms/submit           — completed form → saves to DB
  GET  /api/v1/forms/templates        — pre-built form type templates
  POST /api/v1/forms/upload-image     — upload photo evidence, returns URL
  GET  /api/v1/forms/image/{filename} — serve uploaded photo
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services import db_service as db
from app.services.kb_ingestion import on_form_submission, ingest_async
from app.services.llm_service import _get_client


# ── Severity / type normalisation helpers ─────────────────────────────────────

def _severity_to_p(severity: str) -> str:
    """Map display severity label to IncidentReport P-level."""
    return {"Critical": "P1", "High": "P2", "Medium": "P3", "Low": "P4"}.get(severity, "P5")


def _wo_type_to_category(wo_type: str) -> str:
    """Map form WO type to ManagedWorkOrder category enum."""
    return {"Corrective": "corrective", "Preventive": "preventive",
            "Emergency": "emergency"}.get(wo_type, "corrective")

logger = logging.getLogger(__name__)
router = APIRouter()

FORMS_UPLOAD_DIR = "uploads/forms"
os.makedirs(FORMS_UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic"}

# ── Form field / schema types ─────────────────────────────────────────────────

class FormField(BaseModel):
    id: str
    type: str                  # text|number|date|datetime|textarea|select|checkbox
    label: str
    required: bool = False
    placeholder: str = ""
    default_value: str = ""
    options: list[str] = []    # for select/radio
    unit: str = ""
    hint: str = ""             # shown below the field
    min: float | None = None
    max: float | None = None


class FormSchema(BaseModel):
    form_id: str
    form_type: str             # maintenance_record|sensor_log|incident_report|work_order|equipment_reg
    title: str
    description: str
    equipment_id: str | None
    fields: list[FormField]
    submit_action: str         # same as form_type — controls DB routing on submit


# ── Quick-start templates ─────────────────────────────────────────────────────

TEMPLATES = [
    {
        "id": "tmpl-vib-check",
        "label": "Vibration Check",
        "icon": "activity",
        "description": "Log manual vibration and bearing temperature readings",
        "form_type": "maintenance_record",
        "example_prompt": "log a vibration check for {equipment_id} today",
    },
    {
        "id": "tmpl-lube",
        "label": "Lubrication Record",
        "icon": "droplets",
        "description": "Record lubrication task and oil quantity added",
        "form_type": "maintenance_record",
        "example_prompt": "log lubrication done on {equipment_id}",
    },
    {
        "id": "tmpl-sensor-log",
        "label": "Sensor Log",
        "icon": "gauge",
        "description": "Manually record current sensor readings",
        "form_type": "sensor_log",
        "example_prompt": "record today's sensor readings for {equipment_id}",
    },
    {
        "id": "tmpl-incident",
        "label": "Incident Report",
        "icon": "alert-triangle",
        "description": "Report an equipment failure, near-miss, or process upset",
        "form_type": "incident_report",
        "example_prompt": "report an incident on {equipment_id}",
    },
    {
        "id": "tmpl-wo",
        "label": "Work Order Request",
        "icon": "wrench",
        "description": "Raise a corrective or preventive maintenance work order",
        "form_type": "work_order",
        "example_prompt": "create a work order to fix {equipment_id}",
    },
    {
        "id": "tmpl-equip-reg",
        "label": "Equipment Registration",
        "icon": "plus-circle",
        "description": "Register new equipment in the plant knowledge graph",
        "form_type": "equipment_reg",
        "example_prompt": "register a new pump in the plant",
    },
    {
        "id": "tmpl-defect",
        "label": "Defect Report",
        "icon": "scan-search",
        "description": "Report a physical defect, damage, or anomaly with photo evidence",
        "form_type": "defect_report",
        "example_prompt": "report a defect found on {equipment_id}",
    },
]

# ── LLM form generator ────────────────────────────────────────────────────────

_FORM_SYSTEM = """You are an industrial data capture assistant for an oil refinery operations platform.
Given a plain-language description of what the user wants to record, and optionally the equipment's
current specifications and sensor readings, generate a concise JSON form schema.

Return ONLY valid JSON — no markdown, no extra text — matching this exact schema:
{
  "form_type": "maintenance_record|sensor_log|incident_report|work_order|equipment_reg|defect_report",
  "title": "Short descriptive form title (max 8 words)",
  "description": "One sentence describing what this form captures",
  "fields": [
    {
      "id": "snake_case_field_id",
      "type": "text|number|date|datetime|textarea|select|checkbox|image_upload",
      "label": "Human-readable label",
      "required": true,
      "placeholder": "Example value or hint",
      "default_value": "",
      "options": [],
      "unit": "mm/s",
      "hint": "Normal range or guidance text",
      "min": null,
      "max": null
    }
  ],
  "submit_action": "same as form_type"
}

Rules:
- Always include a 'date' field (type=date, default_value=today) as the first field.
- For maintenance_record: include relevant sensor fields (vibration, temp) if equipment has those readings.
- For sensor_log: include ALL sensor reading fields from the equipment specs.
- For incident_report: include severity (select), symptom (textarea), root_cause (textarea), and ONE image_upload field for photo evidence.
- For work_order: include wo_type (select: Corrective/Preventive/Emergency), description (textarea), priority (select), and ONE image_upload field for site photos.
- For defect_report: include defect_type (select), location (text), severity (select), description (textarea), immediate_action (checkbox), and ONE image_upload field for defect photos. Defect types: Corrosion, Crack/Fracture, Leak, Wear, Mechanical Damage, Electrical Fault, Structural, Process Deviation, Other.
- For equipment_reg: include id, name, type, location, criticality, manufacturer.
- Pre-fill placeholder with the equipment's normal/alarm values as hints.
- Pre-fill technician options if technician names are available.
- image_upload fields: hint should say what photos to attach. default_value = "".
- Maximum 14 fields per form.
"""


async def _llm_generate_form(
    description: str,
    equipment_id: str | None,
    eq_context: dict[str, Any] | None,
) -> dict | None:
    client = _get_client()
    if not client:
        return None
    try:
        context_str = ""
        if eq_context:
            readings = eq_context.get("current_readings") or {}
            specs = eq_context.get("specifications") or {}
            techs = eq_context.get("technicians") or []
            context_str = f"""
Equipment: {eq_context.get('id')} — {eq_context.get('name')} ({eq_context.get('type')})
Location: {eq_context.get('location')}
Technicians: {', '.join(techs) if techs else 'N/A'}
Current readings: {json.dumps(readings, indent=2)}
Specifications: {json.dumps(specs, indent=2)}
"""
        user_msg = f"""User wants to: {description}
{context_str}
Generate the form schema JSON."""

        resp = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _FORM_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=1500,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Form LLM generation failed: %s", exc)
        return None


# ── Heuristic fallback ────────────────────────────────────────────────────────

def _detect_form_type(description: str) -> str:
    d = description.lower()
    if any(k in d for k in ["defect", "crack", "corrosion", "damage", "leak found", "physical damage", "damage found", "anomaly found"]):
        return "defect_report"
    if any(k in d for k in ["incident", "failure", "fault", "near miss", "upset", "emergency", "accident"]):
        return "incident_report"
    if any(k in d for k in ["work order", "corrective", "repair", "fix", "schedule maintenance"]):
        return "work_order"
    if any(k in d for k in ["register", "new equipment", "add equipment", "install"]):
        return "equipment_reg"
    if any(k in d for k in ["sensor", "reading", "log reading", "manual reading"]):
        return "sensor_log"
    return "maintenance_record"   # default


def _heuristic_form(
    description: str,
    equipment_id: str | None,
    eq: dict[str, Any] | None,
    form_type: str,
) -> dict:
    today = date.today().isoformat()
    techs = (eq or {}).get("technicians") or ["Rajesh Kumar", "Amit Shah", "Priya Nair"]
    d_lower = description.lower()
    readings: dict = (eq or {}).get("current_readings") or {}

    base_fields: list[dict] = [
        {"id": "date", "type": "date", "label": "Date", "required": True,
         "default_value": today, "placeholder": today, "unit": "", "hint": "", "options": [], "min": None, "max": None},
    ]
    if equipment_id:
        base_fields.append(
            {"id": "equipment_id", "type": "text", "label": "Equipment ID", "required": True,
             "default_value": equipment_id, "placeholder": "P-101", "unit": "", "hint": "", "options": [], "min": None, "max": None}
        )

    if form_type == "maintenance_record":
        title_kw = "Vibration Check" if "vibration" in d_lower or "vib" in d_lower else \
                   "Lubrication" if any(k in d_lower for k in ["lube", "lubrication", "oil", "grease"]) else \
                   "Bearing Inspection" if "bearing" in d_lower else \
                   "Inspection"
        title = f"{title_kw}{' — ' + equipment_id if equipment_id else ''}"

        fields = list(base_fields)

        # Add sensor fields from equipment's current_readings if available
        reading_fields_added = 0
        for key, r in readings.items():
            if not isinstance(r, dict):
                continue
            label = key.replace("_", " ").title().replace(" De", " DE").replace(" Nde", " NDE")
            alarm_hint = f"Normal: {r.get('normal', '-')} | Alarm: {r.get('alarm', 'N/A')}" if r.get("alarm") else f"Normal: {r.get('normal', '-')}"
            fields.append({
                "id": key, "type": "number", "label": label, "required": False,
                "default_value": "", "placeholder": str(r.get("value", "")),
                "unit": r.get("unit", ""), "hint": alarm_hint,
                "options": [], "min": 0, "max": r.get("trip") or None,
            })
            reading_fields_added += 1
            if reading_fields_added >= 4:
                break

        fields += [
            {"id": "technician", "type": "select", "label": "Technician", "required": True,
             "default_value": "", "placeholder": "", "unit": "", "hint": "",
             "options": techs, "min": None, "max": None},
            {"id": "findings", "type": "textarea", "label": "Findings / Observations", "required": False,
             "default_value": "", "placeholder": "Describe what was found during the inspection…",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
        ]

        return {
            "form_type": "maintenance_record", "title": title,
            "description": f"Log {title_kw.lower()} results for equipment record",
            "fields": fields, "submit_action": "maintenance_record",
        }

    elif form_type == "sensor_log":
        title = f"Sensor Log{' — ' + equipment_id if equipment_id else ''}"
        fields = list(base_fields)
        for key, r in readings.items():
            if not isinstance(r, dict):
                continue
            label = key.replace("_", " ").title().replace(" De", " DE").replace(" Nde", " NDE")
            alarm_hint = f"Normal: {r.get('normal', '-')} | Alarm: {r.get('alarm', 'N/A')}" if r.get("alarm") else f"Normal: {r.get('normal', '-')}"
            fields.append({
                "id": key, "type": "number", "label": label, "required": True,
                "default_value": str(r.get("value", "")),
                "placeholder": str(r.get("value", "")),
                "unit": r.get("unit", ""), "hint": alarm_hint,
                "options": [], "min": 0, "max": r.get("trip") or None,
            })
        fields.append({
            "id": "technician", "type": "select", "label": "Recorded By", "required": True,
            "default_value": "", "placeholder": "", "unit": "", "hint": "",
            "options": techs, "min": None, "max": None,
        })
        return {
            "form_type": "sensor_log", "title": title,
            "description": "Manually log sensor readings for equipment",
            "fields": fields, "submit_action": "sensor_log",
        }

    elif form_type == "incident_report":
        title = f"Incident Report{' — ' + equipment_id if equipment_id else ''}"
        fields = list(base_fields) + [
            {"id": "severity", "type": "select", "label": "Severity", "required": True,
             "default_value": "High", "placeholder": "", "unit": "", "hint": "",
             "options": ["Critical", "High", "Medium", "Low"], "min": None, "max": None},
            {"id": "title", "type": "text", "label": "Incident Title", "required": True,
             "default_value": "", "placeholder": "e.g. Bearing failure — P-101",
             "unit": "", "hint": "Brief descriptive title", "options": [], "min": None, "max": None},
            {"id": "symptom", "type": "textarea", "label": "Symptom / What happened", "required": True,
             "default_value": "", "placeholder": "Describe what was observed…",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "root_cause", "type": "textarea", "label": "Root Cause (if known)", "required": False,
             "default_value": "", "placeholder": "e.g. Lubrication overdue by 12 days…",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "action_taken", "type": "textarea", "label": "Immediate Action Taken", "required": True,
             "default_value": "", "placeholder": "e.g. Emergency shutdown, bearing replaced…",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "downtime_hours", "type": "number", "label": "Downtime (hours)", "required": False,
             "default_value": "0", "placeholder": "0", "unit": "hr", "hint": "",
             "options": [], "min": 0, "max": None},
            {"id": "technician", "type": "select", "label": "Reported By", "required": True,
             "default_value": "", "placeholder": "", "unit": "", "hint": "",
             "options": techs, "min": None, "max": None},
            {"id": "photo_evidence", "type": "image_upload", "label": "Photo Evidence", "required": False,
             "default_value": "", "placeholder": "", "unit": "",
             "hint": "Attach photos of the damage, failure, or site conditions",
             "options": [], "min": None, "max": None},
        ]
        return {
            "form_type": "incident_report", "title": title,
            "description": "Report an equipment failure, near-miss, or process upset",
            "fields": fields, "submit_action": "incident_report",
        }

    elif form_type == "work_order":
        title = f"Work Order{' — ' + equipment_id if equipment_id else ''}"
        fields = list(base_fields) + [
            {"id": "wo_type", "type": "select", "label": "Work Order Type", "required": True,
             "default_value": "Corrective", "placeholder": "", "unit": "", "hint": "",
             "options": ["Corrective", "Preventive", "Emergency"], "min": None, "max": None},
            {"id": "priority", "type": "select", "label": "Priority", "required": True,
             "default_value": "High", "placeholder": "", "unit": "", "hint": "",
             "options": ["Critical", "High", "Medium", "Low"], "min": None, "max": None},
            {"id": "description", "type": "textarea", "label": "Description of Work", "required": True,
             "default_value": "", "placeholder": "Describe what needs to be done…",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "estimated_hours", "type": "number", "label": "Estimated Duration", "required": False,
             "default_value": "4", "placeholder": "4", "unit": "hr", "hint": "",
             "options": [], "min": 0.5, "max": None},
            {"id": "technician", "type": "select", "label": "Assign To", "required": True,
             "default_value": "", "placeholder": "", "unit": "", "hint": "",
             "options": techs, "min": None, "max": None},
            {"id": "spare_parts", "type": "textarea", "label": "Spare Parts Required", "required": False,
             "default_value": "", "placeholder": "e.g. SKF Bearing 6311, Seal Type-2",
             "unit": "", "hint": "List parts, one per line", "options": [], "min": None, "max": None},
            {"id": "site_photos", "type": "image_upload", "label": "Site / Defect Photos", "required": False,
             "default_value": "", "placeholder": "", "unit": "",
             "hint": "Attach photos of the work site, defect, or failed component",
             "options": [], "min": None, "max": None},
        ]
        return {
            "form_type": "work_order", "title": title,
            "description": "Raise a corrective or preventive maintenance work order",
            "fields": fields, "submit_action": "work_order",
        }

    elif form_type == "defect_report":   # ── NEW ──
        _dash = " \u2014 "
        title = f"Defect Report{(_dash + equipment_id) if equipment_id else ''}"
        fields = list(base_fields) + [
            {"id": "defect_type", "type": "select", "label": "Defect Type", "required": True,
             "default_value": "Other", "placeholder": "", "unit": "", "hint": "",
             "options": ["Corrosion", "Crack / Fracture", "Leak", "Wear",
                         "Mechanical Damage", "Electrical Fault", "Structural",
                         "Process Deviation", "Other"],
             "min": None, "max": None},
            {"id": "severity", "type": "select", "label": "Severity", "required": True,
             "default_value": "High", "placeholder": "", "unit": "", "hint": "",
             "options": ["Critical", "High", "Medium", "Low"], "min": None, "max": None},
            {"id": "location_on_equipment", "type": "text", "label": "Location on Equipment", "required": True,
             "default_value": "", "placeholder": "e.g. Drive-end bearing housing, flange weld, nozzle N3",
             "unit": "", "hint": "Be specific — this helps maintenance team locate the defect",
             "options": [], "min": None, "max": None},
            {"id": "description", "type": "textarea", "label": "Defect Description", "required": True,
             "default_value": "", "placeholder": "Describe size, depth, extent, and any progression observed…",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "immediate_action_required", "type": "checkbox", "label": "Requires Immediate Action",
             "required": False, "default_value": "false",
             "placeholder": "Check if this defect poses immediate safety or operational risk",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "reported_by", "type": "select", "label": "Reported By", "required": True,
             "default_value": "", "placeholder": "", "unit": "", "hint": "",
             "options": techs, "min": None, "max": None},
            {"id": "defect_photos", "type": "image_upload", "label": "Defect Photos", "required": True,
             "default_value": "", "placeholder": "", "unit": "",
             "hint": "Attach clear photos showing the defect. Multiple angles recommended.",
             "options": [], "min": None, "max": None},
        ]
        return {
            "form_type": "defect_report", "title": title,
            "description": "Document a physical defect, damage, or anomaly with photo evidence",
            "fields": fields, "submit_action": "defect_report",
        }

    else:  # equipment_reg
        title = "New Equipment Registration"
        fields = [
            {"id": "id", "type": "text", "label": "Equipment Tag / ID", "required": True,
             "default_value": "", "placeholder": "e.g. P-301",
             "unit": "", "hint": "Use plant tagging convention", "options": [], "min": None, "max": None},
            {"id": "name", "type": "text", "label": "Equipment Name", "required": True,
             "default_value": "", "placeholder": "e.g. Reflux Pump",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "type", "type": "select", "label": "Equipment Type", "required": True,
             "default_value": "Centrifugal Pump", "placeholder": "",
             "unit": "", "hint": "",
             "options": ["Centrifugal Pump", "Reciprocating Pump", "Compressor", "Heat Exchanger",
                         "Vessel", "Column", "Furnace", "Motor", "Valve", "Other"],
             "min": None, "max": None},
            {"id": "location", "type": "text", "label": "Location / Unit", "required": True,
             "default_value": "", "placeholder": "e.g. Unit 4 — CDU",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "criticality", "type": "select", "label": "Criticality", "required": True,
             "default_value": "High", "placeholder": "",
             "unit": "", "hint": "",
             "options": ["Critical", "High", "Medium", "Low"],
             "min": None, "max": None},
            {"id": "manufacturer", "type": "text", "label": "Manufacturer", "required": False,
             "default_value": "", "placeholder": "e.g. Flowserve",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "model", "type": "text", "label": "Model Number", "required": False,
             "default_value": "", "placeholder": "e.g. PVXM-100",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
            {"id": "installed_date", "type": "date", "label": "Installation Date", "required": False,
             "default_value": "", "placeholder": "",
             "unit": "", "hint": "", "options": [], "min": None, "max": None},
        ]
        return {
            "form_type": "equipment_reg", "title": title,
            "description": "Register new equipment in the plant knowledge base",
            "fields": fields, "submit_action": "equipment_reg",
        }


# ── Request / Response schemas ────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    description: str
    equipment_id: str | None = None


class SubmitRequest(BaseModel):
    form_type: str
    equipment_id: str | None = None
    field_values: dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates():
    """Return quick-start form templates."""
    return TEMPLATES


@router.post("/generate")
async def generate_form(body: GenerateRequest) -> FormSchema:
    """
    Generate a form schema from a plain-language description.
    Uses GPT-4.1 when available, falls back to heuristics.
    """
    if not body.description.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="description must not be empty")

    eq: dict | None = None
    if body.equipment_id:
        eq = await db.get_equipment(body.equipment_id)

    result = await _llm_generate_form(body.description, body.equipment_id, eq)

    if result is None:
        form_type = _detect_form_type(body.description)
        result = _heuristic_form(body.description, body.equipment_id, eq, form_type)

    form_id = f"FORM-{uuid.uuid4().hex[:8].upper()}"
    fields = [FormField(**f) for f in result.get("fields", [])]

    return FormSchema(
        form_id=form_id,
        form_type=result.get("form_type", "maintenance_record"),
        title=result.get("title", "Data Entry Form"),
        description=result.get("description", ""),
        equipment_id=body.equipment_id,
        fields=fields,
        submit_action=result.get("submit_action", "maintenance_record"),
    )


@router.post("/submit")
async def submit_form(body: SubmitRequest):
    """
    Submit completed form data to the appropriate DB table.
    Routes based on form_type.
    """
    vals = body.field_values
    eq_id = body.equipment_id or vals.get("equipment_id") or "UNKNOWN"
    record_id = f"FORM-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.utcnow().isoformat()

    # Fields that are never sensor readings
    _NON_SENSOR = {"date", "equipment_id", "technician", "findings", "description",
                   "photo_evidence", "site_photos", "defect_photos", "attachments"}

    if body.form_type == "maintenance_record":
        record: dict[str, Any] = {
            "id": record_id,
            "equipment_id": eq_id,
            "date": vals.get("date", date.today().isoformat()),
            "type": "Manual Entry",
            "description": vals.get("findings") or vals.get("description") or "Form-submitted maintenance record",
            "status": "Completed",
            "technician": vals.get("technician"),
        }
        sensor_updates: dict[str, float] = {}
        for key in vals:
            if key not in _NON_SENSOR:
                try:
                    v = float(vals[key]) if vals[key] else None
                    record[key] = v
                    if v is not None:
                        sensor_updates[key] = v
                except (ValueError, TypeError):
                    record[key] = vals[key]
        await db.upsert_maintenance_record(record)
        # Reflect new readings in live equipment current_readings
        if sensor_updates and eq_id != "UNKNOWN":
            await db.update_equipment_sensor_values(eq_id, sensor_updates)
        return {"id": record_id, "message": "Maintenance record saved", "form_type": "maintenance_record"}

    elif body.form_type == "sensor_log":
        record = {
            "id": record_id,
            "equipment_id": eq_id,
            "date": vals.get("date", date.today().isoformat()),
            "type": "Sensor Log",
            "description": f"Manual sensor log by {vals.get('technician', 'operator')}",
            "status": "Completed",
            "technician": vals.get("technician"),
        }
        sensor_updates_sl: dict[str, float] = {}
        for key in vals:
            if key not in _NON_SENSOR | {"technician"}:
                try:
                    v = float(vals[key]) if vals[key] else None
                    record[key] = v
                    if v is not None:
                        sensor_updates_sl[key] = v
                except (ValueError, TypeError):
                    record[key] = vals[key]
        await db.upsert_maintenance_record(record)
        # ── Update live equipment current_readings ──────────────────────────
        if sensor_updates_sl and eq_id != "UNKNOWN":
            await db.update_equipment_sensor_values(eq_id, sensor_updates_sl)
        updated_sensors = list(sensor_updates_sl.keys())
        return {
            "id": record_id,
            "message": f"Sensor log saved — {len(updated_sensors)} reading(s) updated",
            "form_type": "sensor_log",
            "updated_sensors": updated_sensors,
        }

    elif body.form_type == "incident_report":
        inc_record: dict[str, Any] = {
            "id": record_id,
            "equipment_id": eq_id,
            "date": vals.get("date", date.today().isoformat()),
            "title": vals.get("title") or f"Incident on {eq_id}",
            "severity": vals.get("severity", "Medium"),
            "symptom": vals.get("symptom", ""),
            "root_cause": vals.get("root_cause") or None,
            "action_taken": vals.get("action_taken") or None,
            "downtime_hours": float(vals.get("downtime_hours", 0) or 0),
            "technician": vals.get("technician"),
            "keywords": [],
        }
        # Legacy Incident table (AI agents + KB queries)
        await db.upsert_incident(inc_record)

        # IncidentReport table — makes it visible in the Incidents workflow UI
        await db.upsert_incident_report({
            "id": f"IR-{record_id}",
            "incident_number": f"INC-FORM-{record_id[:8]}",
            "title": inc_record["title"],
            "description": vals.get("symptom", ""),
            "incident_type": "other",
            "severity": _severity_to_p(vals.get("severity", "Medium")),
            "status": "reported",
            "equipment_ids": [eq_id] if eq_id != "UNKNOWN" else [],
            "occurred_at": vals.get("date"),
            "reported_at": now,
            "reported_by_name": vals.get("technician"),
            "immediate_actions": [vals.get("action_taken")] if vals.get("action_taken") else [],
            "downtime_hours": float(vals.get("downtime_hours", 0) or 0) or None,
            "cost_usd": None,
        })
        # ── KB: add to knowledge graph so AI agents reference this incident ──
        ingest_async(on_form_submission("incident_report", eq_id, record_id, vals))
        return {"id": record_id, "message": "Incident report saved", "form_type": "incident_report"}

    elif body.form_type == "work_order":
        wo_data: dict[str, Any] = {
            "id": f"WO-{uuid.uuid4().hex[:8].upper()}",
            "equipment_id": eq_id,
            "query_text": vals.get("description", "Form-submitted work order"),
            "risk_level": vals.get("priority", "High"),
            "wo_type": vals.get("wo_type", "Corrective"),
            "description": vals.get("description", ""),
            "estimated_duration_hours": float(vals.get("estimated_hours", 4) or 4),
            "required_technicians": 1,
            "steps": [],
            "spare_parts": [p.strip() for p in (vals.get("spare_parts") or "").split("\n") if p.strip()],
            "safety_precautions": [],
            "required_permits": ["PTW Class C — Machinery"],
            "status": "open",
        }
        wo_id = await db.create_work_order(wo_data)

        # ManagedWorkOrder table — visible in the Managed Work Orders workflow UI
        mwo_number = f"WO-FORM-{uuid.uuid4().hex[:6].upper()}"
        await db.upsert_managed_work_order({
            "wo_number": mwo_number,
            "title": (vals.get("description") or f"Work Order — {eq_id}")[:120],
            "description": vals.get("description", ""),
            "category": _wo_type_to_category(vals.get("wo_type", "Corrective")),
            "priority": (vals.get("priority") or "High").lower(),
            "status": "draft",
            "equipment_ids": [eq_id] if eq_id != "UNKNOWN" else [],
            "estimated_hours": float(vals.get("estimated_hours", 4) or 4),
            "created_by_name": vals.get("technician"),
            "materials": [
                {"description": p.strip(), "qty_required": 1, "unit": "ea"}
                for p in (vals.get("spare_parts") or "").split("\n") if p.strip()
            ],
        })
        # ── KB: register WO in knowledge graph ──
        ingest_async(on_form_submission("work_order", eq_id, wo_id, vals))
        return {"id": wo_id, "message": "Work order created", "form_type": "work_order"}

    elif body.form_type == "equipment_reg":
        eq_record: dict[str, Any] = {
            "id": vals.get("id", record_id),
            "name": vals.get("name", "Unknown Equipment"),
            "type": vals.get("type", "Unknown"),
            "location": vals.get("location", ""),
            "criticality": vals.get("criticality", "High"),
            "manufacturer": vals.get("manufacturer") or None,
            "model": vals.get("model") or None,
            "installed_date": vals.get("installed_date") or None,
            "health_score": None,
            "failure_probability": None,
            "compliance_score": None,
            "maintenance_due_days": None,
            "status": "Registered",
        }
        await db.upsert_equipment(eq_record)
        await db.upsert_graph_node({
            "id": eq_record["id"],
            "name": f"{eq_record['id']}\n{eq_record['type']}",
            "type": "equipment",
            "val": 16,
        })
        return {"id": eq_record["id"], "message": "Equipment registered", "form_type": "equipment_reg"}

    elif body.form_type == "defect_report":
        defect_record: dict[str, Any] = {
            "id": record_id,
            "equipment_id": eq_id,
            "date": vals.get("date", date.today().isoformat()),
            "title": f"Defect: {vals.get('defect_type', 'Unknown')} on {eq_id}",
            "severity": vals.get("severity", "High"),
            "symptom": (
                f"{vals.get('defect_type', 'Defect')} at {vals.get('location_on_equipment', 'N/A')}. "
                f"{vals.get('description', '')}"
            ),
            "root_cause": vals.get("defect_type") or None,
            "action_taken": "Immediate action required" if vals.get("immediate_action_required") == "true" else "Scheduled for review",
            "technician": vals.get("reported_by"),
            "keywords": [vals.get("defect_type", "defect").lower(), "defect", "inspection"],
            "downtime_hours": 0,
        }
        # Legacy Incident table (AI agents + KB queries)
        await db.upsert_incident(defect_record)

        # IncidentReport table — makes it visible in the Incidents workflow UI
        await db.upsert_incident_report({
            "id": f"IR-{record_id}",
            "incident_number": f"DEF-FORM-{record_id[:8]}",
            "title": defect_record["title"],
            "description": defect_record["symptom"],
            "incident_type": "property_damage",
            "severity": _severity_to_p(vals.get("severity", "High")),
            "status": "reported",
            "equipment_ids": [eq_id] if eq_id != "UNKNOWN" else [],
            "occurred_at": vals.get("date"),
            "reported_at": now,
            "reported_by_name": vals.get("reported_by"),
            "location_description": vals.get("location_on_equipment"),
            "immediate_actions": ["Immediate action required"] if vals.get("immediate_action_required") == "true" else [],
        })
        # ── KB: add defect to knowledge graph with location + photo metadata ──
        ingest_async(on_form_submission("defect_report", eq_id, record_id, vals))
        return {"id": record_id, "message": "Defect report saved", "form_type": "defect_report"}

    return {"id": record_id, "message": "Form submitted", "form_type": body.form_type}


# ── Image upload / serve ──────────────────────────────────────────────────────

@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload a photo for use as form evidence (defect, incident, work order).
    Returns the URL path to embed in form values.
    Accepts: jpg, jpeg, png, webp, gif, bmp, tiff, heic.
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="No filename provided")

    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type '{ext}'. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(FORMS_UPLOAD_DIR, safe_name)

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:   # 20 MB cap
        raise HTTPException(status_code=413, detail="Image too large (max 20 MB)")

    with open(dest, "wb") as f:
        f.write(content)

    logger.info("Form image saved: %s (%d bytes)", safe_name, len(content))
    return {
        "url": f"/api/v1/forms/image/{safe_name}",
        "filename": safe_name,
        "original_name": file.filename,
        "size_bytes": len(content),
    }


@router.get("/image/{filename}")
async def serve_image(filename: str):
    """Serve a previously uploaded form image."""
    # Sanitise: no path traversal
    safe = os.path.basename(filename)
    path = os.path.join(FORMS_UPLOAD_DIR, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)
